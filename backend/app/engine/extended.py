"""Versioned CPU, memory and task experiment. Historical results use runner.py."""

from __future__ import annotations

import csv
import hashlib
import io
import time
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from math import ceil, isfinite

import numpy as np

from app.engine.csv_loader import MAX_CSV_BYTES
from app.engine.diagnostics import MAX_POINTS, sample_indices
from app.engine.features import MIN_HISTORY_REQUIRED, MIN_WORKLOAD_SERVICES, MIN_WORKLOAD_STEPS
from app.engine.generator import generate_workload
from app.engine.runner import _check_deadline, run_split_pipeline
from app.engine.task_scheduler import INTERVAL_SECONDS, Task, run_service, task_metrics
from app.workload_limits import EXTENDED_MAX_SERVICES as MAX_SERVICES
from app.workload_limits import EXTENDED_MAX_STEPS as MAX_STEPS

MODE = "extended-v1"
MAX_RESOURCE_VALUE = 65_536
REQUIRED_COLUMNS = ("service_id", "timestamp", "cpu_demand", "memory_demand_gib")


def check_size(n_services: int, n_steps: int) -> None:
    if not MIN_WORKLOAD_SERVICES <= n_services <= MAX_SERVICES:
        raise ValueError(f"Use {MIN_WORKLOAD_SERVICES}–{MAX_SERVICES} services.")
    if not MIN_WORKLOAD_STEPS <= n_steps <= MAX_STEPS:
        raise ValueError(f"Use {MIN_WORKLOAD_STEPS}–{MAX_STEPS} five-minute observations.")


def parse_extended_csv(content: bytes) -> tuple[np.ndarray, np.ndarray]:
    if len(content) > MAX_CSV_BYTES:
        raise ValueError("CSV exceeds the 5 MiB limit.")
    try:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")), strict=True)
        header = reader.fieldnames or []
        if not set(REQUIRED_COLUMNS).issubset(header) or len(set(header)) != len(header):
            raise ValueError("CSV requires unique columns: " + ", ".join(REQUIRED_COLUMNS))
        records: dict[str, dict[int | datetime, tuple[float, float]]] = defaultdict(dict)
        timestamp_kind = None
        for row in reader:
            service = (row.get("service_id") or "").strip()
            label = (row.get("timestamp") or "").strip()
            if not service or not label or None in row:
                raise ValueError(f"Line {reader.line_num}: expected one complete observation.")
            key: int | datetime
            if label.isascii() and label.isdecimal():
                key = int(label)
            else:
                try:
                    key = datetime.fromisoformat(label)
                    if key.tzinfo is None:
                        raise ValueError
                    key = key.astimezone(UTC)
                except (ValueError, OverflowError) as exc:
                    raise ValueError(
                        f"Line {reader.line_num}: use a nonnegative interval index or "
                        "an ISO-8601 timestamp with an offset."
                    ) from exc
            if timestamp_kind is None:
                timestamp_kind = type(key)
            if type(key) is not timestamp_kind:
                raise ValueError("Use one timestamp format throughout the file.")
            try:
                cpu = float(row["cpu_demand"])
                memory = float(row["memory_demand_gib"])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Line {reader.line_num}: demand must be numeric.") from exc
            if not all(isfinite(v) and 0 <= v <= MAX_RESOURCE_VALUE for v in (cpu, memory)):
                raise ValueError(
                    f"Line {reader.line_num}: demand must be finite and within "
                    f"[0, {MAX_RESOURCE_VALUE}]."
                )
            series = records[service]
            if key in series:
                raise ValueError(f"Line {reader.line_num}: duplicate service and interval.")
            series[key] = (cpu, memory)
            if len(series) > MAX_STEPS or len(records) > MAX_SERVICES:
                raise ValueError("CSV exceeds the extended experiment workload limits.")
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ValueError("Upload a valid UTF-8 CSV.") from exc

    if not records:
        raise ValueError("CSV contains no observations.")
    service_order = sorted(records)
    grid = sorted(records[service_order[0]])
    check_size(len(records), len(grid))
    increment = 1 if timestamp_kind is int else timedelta(seconds=INTERVAL_SECONDS)
    if any(b - a != increment for a, b in zip(grid[:-1], grid[1:], strict=True)):
        raise ValueError("Each series must use consecutive five-minute intervals.")
    if any(series.keys() != records[service_order[0]].keys() for series in records.values()):
        raise ValueError("Every service must cover the same timestamp grid.")
    values = np.array([[records[service][step] for step in grid] for service in service_order])
    return values[:, :, 0], values[:, :, 1]


def synthetic_memory(cpu: np.ndarray, seed: int) -> np.ndarray:
    rng = np.random.default_rng(np.random.SeedSequence([seed, 1]))
    n_services, n_steps = cpu.shape
    elapsed = np.arange(n_steps)
    memory = np.empty_like(cpu)
    for index in range(n_services):
        base = rng.uniform(2, 24)
        phase = rng.uniform(0, 2 * np.pi)
        daily = 0.20 * base * np.sin(elapsed * 2 * np.pi / 288 + phase)
        weekly = 0.07 * base * np.sin(elapsed * 2 * np.pi / 2016)
        series = base + daily + weekly + 0.12 * cpu[index]
        series += rng.normal(0, 0.06 * base, n_steps)
        for start in np.flatnonzero(rng.random(n_steps) < 0.013):
            series[start : start + rng.integers(2, 12)] += rng.uniform(0.2, 0.7) * base
        for start in np.flatnonzero(rng.random(n_steps) < 0.003):
            series[start : start + rng.integers(36, 160)] += rng.uniform(0.25, 0.65) * base
        memory[index] = np.maximum(0.05, series)
    return memory


def causal_reference(demand: np.ndarray) -> np.ndarray:
    return np.maximum(0.05, 1.30 * np.max(demand[:, :MIN_HISTORY_REQUIRED], axis=1))


def offered_tasks(
    cpu: np.ndarray, memory: np.ndarray, services: np.ndarray, start: int, seed: int
) -> list[list[Task]]:
    offered = []
    for service in services:
        rng = np.random.default_rng(np.random.SeedSequence([seed, int(service), 2]))
        work_mix = rng.uniform(0.70, 1.30, cpu.shape[1])
        memory_mix = rng.uniform(0.20, 0.75, cpu.shape[1])
        offered.append(
            [
                Task(
                    f"{service}:{step}",
                    int(service),
                    (step - start) * INTERVAL_SECONDS,
                    float(max(0.01, cpu[service, step] * INTERVAL_SECONDS * work_mix[step])),
                    float(max(0.0, memory[service, step] * memory_mix[step])),
                )
                for step in range(start, cpu.shape[1])
            ]
        )
    return offered


def simulate_policy(
    tasks: list[list[Task]], cpu: np.ndarray, memory: np.ndarray, deadline: float
) -> dict:
    states = []
    backlog = np.zeros(cpu.shape[1], dtype=int)
    completed_by_step = np.zeros(cpu.shape[1], dtype=int)
    cpu_used = memory_used = 0.0
    for jobs, cpu_service, memory_service in zip(tasks, cpu, memory, strict=True):
        _check_deadline(deadline, "task simulation")
        usage = []
        service_states, service_backlog = run_service(
            jobs, cpu_service, memory_service, usage=usage
        )
        cpu_used += sum(row.cpu_core_seconds for row in usage)
        memory_used += sum(row.memory_gib_seconds for row in usage)
        states.extend(service_states)
        backlog += service_backlog
        for state in service_states:
            if state.completion is not None:
                step = max(0, ceil(state.completion / INTERVAL_SECONDS) - 1)
                completed_by_step[step] += 1
    summary = task_metrics(states, backlog.tolist(), len(backlog) * INTERVAL_SECONDS)
    cpu_capacity = float(cpu.sum()) * INTERVAL_SECONDS
    memory_capacity = float(memory.sum()) * INTERVAL_SECONDS
    summary["scheduler_utilization"] = {
        "cpu_core_seconds": cpu_used,
        "cpu_capacity_core_seconds": cpu_capacity,
        "cpu_fraction": cpu_used / cpu_capacity if cpu_capacity else None,
        "memory_gib_seconds": memory_used,
        "memory_capacity_gib_seconds": memory_capacity,
        "memory_fraction": memory_used / memory_capacity if memory_capacity else None,
    }
    # Per-bin throughput uses every observed completion. Backlog is sampled at the bin end.
    chunks = np.array_split(np.arange(len(backlog)), min(MAX_POINTS, len(backlog)))
    summary["timeline"] = [
        {
            "elapsed_seconds": int((chunk[-1] + 1) * INTERVAL_SECONDS),
            "backlog": int(backlog[chunk[-1]]),
            "throughput_per_second": float(
                completed_by_step[chunk].sum() / (len(chunk) * INTERVAL_SECONDS)
            ),
        }
        for chunk in chunks
    ]
    summary["task_samples"] = [
        {
            "id": state.task.id,
            "service_index": state.task.service,
            "arrival_seconds": state.task.arrival,
            "cpu_core_seconds": state.task.cpu_core_seconds,
            "memory_gib": state.task.memory_gib,
            "start_seconds": state.start,
            "first_service_seconds": state.first_service,
            "completion_seconds": state.completion,
            "rejected": state.rejected,
        }
        for state in (states[index] for index in sample_indices(len(states), 16))
    ]
    return summary


def evaluate_resources(
    cpu: np.ndarray,
    memory: np.ndarray,
    seed: int,
    target: float,
    deadline: float,
    split: dict,
    n_estimators_override: int | None,
    diagnostics: bool,
    rf_jobs: int = -1,
) -> dict:
    validation_cpu = {}
    test_cpu = {}
    allocations_cpu = {}

    def collect_cpu(name, validation, test, allocation):
        validation_cpu[name] = validation
        test_cpu[name] = test
        allocations_cpu[name] = allocation

    common = dict(
        **split,
        target_violation=target,
        deadline=deadline,
        n_estimators_override=n_estimators_override,
        include_diagnostics=diagnostics,
        include_service_metrics=False,
        rf_jobs=rf_jobs,
    )
    cpu_result = run_split_pipeline(
        cpu, causal_reference(cpu), **common, observe_allocations=collect_cpu
    )
    tasks = offered_tasks(cpu, memory, split["test_services"], split["test_start"], seed)
    digest = hashlib.sha256()
    for index, jobs in enumerate(tasks):
        if index:
            digest.update(b"\n")
        digest.update("\n".join(map(repr, jobs)).encode())
    shape = (len(tasks), len(tasks[0]))
    policies = {}

    def compare_memory(name, validation, test, allocation):
        if name not in validation_cpu:
            return
        val_rate = float(np.mean(validation_cpu.pop(name) | validation))
        feasible = val_rate <= target
        cpu_violations = test_cpu.pop(name)
        cpu_allocation = allocations_cpu.pop(name)
        policies[name] = {
            "validation_joint_violation_rate": val_rate,
            "test_joint_violation_rate": float(np.mean(cpu_violations | test)),
            "jointly_feasible": feasible,
            "tasks": simulate_policy(
                tasks,
                cpu_allocation.reshape(shape),
                allocation.reshape(shape),
                deadline,
            )
            if feasible or name == "static"
            else None,
        }

    memory_result = run_split_pipeline(
        memory,
        causal_reference(memory),
        **common,
        observe_allocations=compare_memory,
    )
    for result in (cpu_result, memory_result):
        result["methods"]["static"].update(mae=None, mse=None, rmse=None)
    for name in cpu_result["methods"]:
        policies.setdefault(
            name,
            {
                "jointly_feasible": False,
                "validation_joint_violation_rate": None,
                "test_joint_violation_rate": None,
                "tasks": None,
            },
        )
    return {
        "cpu": cpu_result,
        "memory": memory_result,
        "policies": policies,
        "offered_tasks_sha256": digest.hexdigest(),
        "offered_tasks": sum(map(len, tasks)),
    }


def run_extended(
    seed: int = 42,
    n_services: int = 4,
    n_steps: int = 600,
    target_violation: float = 0.01,
    timeout_seconds: float = 60,
    workload: tuple[np.ndarray, np.ndarray] | None = None,
    n_estimators_override: int | None = None,
    diagnostics: bool = True,
    rf_jobs: int = -1,
) -> dict:
    started = time.time()
    deadline = started + timeout_seconds
    if workload is None:
        check_size(n_services, n_steps)
        cpu = generate_workload(seed, n_services, n_steps).demand
        memory = synthetic_memory(cpu, seed)
    else:
        cpu, memory = workload
        if cpu.ndim != 2 or cpu.shape != memory.shape:
            raise ValueError("CPU and memory must share one aligned service-time grid.")
        n_services, n_steps = cpu.shape
        check_size(n_services, n_steps)
        if any(np.any(~np.isfinite(a) | (a < 0) | (a > MAX_RESOURCE_VALUE)) for a in workload):
            raise ValueError("Resource demand is outside the supported numeric range.")
    services = np.arange(n_services)
    train_count = max(1, int(0.60 * n_services))
    val_count = max(1, int(0.15 * n_services))
    train_end, val_end = int(0.60 * n_steps), int(0.75 * n_steps)
    splits = {
        "time_split": dict(
            train_services=services,
            val_services=services,
            test_services=services,
            train_start=MIN_HISTORY_REQUIRED,
            train_end=train_end,
            val_start=train_end,
            val_end=val_end,
            test_start=val_end,
            test_end=n_steps,
        ),
        "service_split": dict(
            train_services=services[:train_count],
            val_services=services[train_count : train_count + val_count],
            test_services=services[train_count + val_count :],
            train_start=MIN_HISTORY_REQUIRED,
            train_end=n_steps,
            val_start=MIN_HISTORY_REQUIRED,
            val_end=n_steps,
            test_start=MIN_HISTORY_REQUIRED,
            test_end=n_steps,
        ),
    }
    results = {
        key: evaluate_resources(
            cpu,
            memory,
            seed,
            target_violation,
            deadline,
            split,
            n_estimators_override,
            diagnostics,
            rf_jobs,
        )
        for key, split in splits.items()
    }
    _check_deadline(deadline, "extended reporting")
    return {
        "mode": MODE,
        "execution_time_seconds": round(time.time() - started, 3),
        "parameters": {
            "seed": seed,
            "n_services": n_services,
            "n_steps": n_steps,
            "target_violation": target_violation,
        },
        **results,
    }
