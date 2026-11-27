"""Deterministic per-service task scheduling over fixed capacity intervals."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from math import isfinite

import numpy as np

INTERVAL_SECONDS = 300
QUEUE_LIMIT = 32
ADMITTED_LIMIT = 32


@dataclass(frozen=True)
class Task:
    id: str
    service: int
    arrival: float
    cpu_core_seconds: float
    memory_gib: float


@dataclass
class TaskState:
    task: Task
    remaining: float
    start: float | None = None
    first_service: float | None = None
    completion: float | None = None
    rejected: bool = False
    suspended: bool = False


@dataclass(frozen=True)
class IntervalUsage:
    cpu_core_seconds: float
    memory_gib_seconds: float


def run_service(
    tasks: list[Task],
    cpu: np.ndarray,
    memory: np.ndarray,
    interval_seconds: float = INTERVAL_SECONDS,
    queue_limit: int = QUEUE_LIMIT,
    *,
    usage: list[IntervalUsage] | None = None,
) -> tuple[list[TaskState], list[int]]:
    """Execute one FIFO service, with exact completion events inside each interval."""
    if (
        cpu.ndim != 1
        or cpu.shape != memory.shape
        or not len(cpu)
        or not np.all(np.isfinite(cpu))
        or not np.all(np.isfinite(memory))
        or np.any(cpu < 0)
        or np.any(memory < 0)
        or not isfinite(interval_seconds)
        or interval_seconds <= 0
        or queue_limit < 1
    ):
        raise ValueError("Invalid capacity schedule or interval.")
    arrivals: dict[int, list[TaskState]] = {}
    if len({task.id for task in tasks}) != len(tasks) or len({t.service for t in tasks}) > 1:
        raise ValueError("Use unique task identifiers and one service per schedule.")
    states = [TaskState(task, task.cpu_core_seconds) for task in tasks]
    for state in sorted(states, key=lambda state: (state.task.arrival, state.task.id)):
        task = state.task
        if (
            not all(map(isfinite, (task.arrival, task.memory_gib, task.cpu_core_seconds)))
            or not 0 <= task.arrival < len(cpu) * interval_seconds
            or task.arrival % interval_seconds != 0
            or task.memory_gib < 0
            or task.cpu_core_seconds <= 0
        ):
            raise ValueError("Tasks require grid-aligned arrivals and valid resource requirements.")
        arrivals.setdefault(int(task.arrival / interval_seconds), []).append(state)

    waiting: deque[TaskState] = deque()
    admitted: list[TaskState] = []
    backlog = []
    for step, (cores, gib) in enumerate(zip(cpu, memory, strict=True)):
        now = step * interval_seconds
        end = now + interval_seconds
        for state in arrivals.get(step, ()):
            if len(waiting) == queue_limit:
                state.rejected = True
            else:
                waiting.append(state)
        active: list[TaskState] = []
        suspended: deque[TaskState] = deque()
        available = float(gib)
        cpu_used = 0.0
        memory_used = 0.0
        for state in admitted:
            if state.task.memory_gib <= available:
                state.suspended = False
                active.append(state)
                available -= state.task.memory_gib
            else:
                state.suspended = True
                suspended.append(state)

        while now < end:
            while suspended and suspended[0].task.memory_gib <= available:
                state = suspended.popleft()
                state.suspended = False
                available -= state.task.memory_gib
                active.append(state)
            while (
                not suspended
                and waiting
                and len(admitted) < ADMITTED_LIMIT
                and waiting[0].task.memory_gib <= available
            ):
                state = waiting.popleft()
                state.start = now
                admitted.append(state)
                available -= state.task.memory_gib
                active.append(state)
            resident = float(gib) - available
            if not active or cores == 0:
                memory_used += resident * (end - now)
                break
            rate = float(cores) / len(active)
            remaining_time = end - now
            finish_after = min(state.remaining for state in active) / rate
            duration = min(remaining_time, finish_after)
            memory_used += resident * duration
            completed = []
            for state in active:
                if state.first_service is None:
                    state.first_service = now
                if state.remaining / rate == duration:
                    cpu_used += state.remaining
                    state.remaining = 0.0
                    state.completion = now + duration
                    available += state.task.memory_gib
                    completed.append(state.task.id)
                else:
                    progress = min(state.remaining, rate * duration)
                    cpu_used += progress
                    state.remaining -= progress
            now += duration
            if completed:
                complete_ids = set(completed)
                active = [state for state in active if state.task.id not in complete_ids]
                admitted = [state for state in admitted if state.task.id not in complete_ids]
        backlog.append(len(waiting) + len(suspended))
        if usage is not None:
            usage.append(IntervalUsage(cpu_used, memory_used))
    return states, backlog


def task_metrics(states: list[TaskState], backlog: list[int], seconds: float) -> dict:
    completed = [s for s in states if s.completion is not None]
    durations = {
        "waiting": [s.start - s.task.arrival for s in states if s.start is not None],
        "first_service": [
            s.first_service - s.task.arrival for s in states if s.first_service is not None
        ],
        "response": [s.completion - s.task.arrival for s in completed],
        "execution": [s.completion - s.start for s in completed],
    }
    timing = {
        key: {
            "count": len(values),
            "mean": float(np.mean(values)) if values else None,
            "median": float(np.median(values)) if values else None,
            "p95": float(np.percentile(values, 95)) if values else None,
        }
        for key, values in durations.items()
    }
    counts, edges = np.histogram(durations["response"], bins=12) if completed else ([], [])
    rejected = sum(s.rejected for s in states)
    return {
        "offered": len(states),
        "completed": len(completed),
        "completion_rate": len(completed) / len(states) if states else None,
        "unfinished": len(states) - len(completed),
        "rejected": rejected,
        "admitted_unfinished": sum(s.start is not None and s.completion is None for s in states),
        "suspended_final": sum(s.suspended for s in states),
        "never_admitted": sum(s.start is None and not s.rejected for s in states),
        "throughput_per_second": len(completed) / seconds,
        "peak_backlog": max(backlog, default=0),
        "final_backlog": backlog[-1] if backlog else 0,
        "timing_seconds": timing,
        "response_distribution": {
            "edges": list(map(float, edges)),
            "counts": list(map(int, counts)),
        },
    }
