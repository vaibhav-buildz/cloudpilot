"""Verify the controlled extended-v1 rollout through the hosted Vercel proxy."""

from __future__ import annotations

import csv
import io
import math
import uuid
from pathlib import Path
from time import perf_counter

import httpx

from smoke_test import _require_env

MODE = "extended-v1"
WORKLOAD = {"mode": MODE, "n_services": 4, "n_steps": 600, "seed": 42}
SAMPLE = Path(__file__).resolve().parents[1] / "frontend/public/sample-workload.csv"


class SmokeFailure(Exception):
    """A diagnostic built from static labels and numeric status codes."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def expect_status(response: httpx.Response, status: int) -> None:
    require(
        response.status_code == status,
        f"expected HTTP {status}, got {response.status_code}",
    )


def nonnegative(value: float) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def check_result(result: dict) -> None:
    require(result["mode"] == MODE, "unexpected result mode")
    for key in ("n_services", "n_steps"):
        require(result["parameters"][key] == WORKLOAD[key], f"unexpected {key}")
    require(nonnegative(result["execution_time_seconds"]), "invalid engine time")
    for split_name in ("time_split", "service_split"):
        split = result[split_name]
        for resource in ("cpu", "memory"):
            comparison = split[resource]
            model = comparison["methods"]["GBR_q95"]
            require(
                all(nonnegative(model[key]) for key in ("mae", "mse", "rmse"))
                and math.isclose(model["rmse"] ** 2, model["mse"], rel_tol=1e-8),
                f"{split_name} {resource} prediction errors",
            )
            traces = comparison["traces"]
            require(bool(traces), f"{split_name} {resource} traces missing")
            for trace in traces:
                points = len(trace["steps"])
                for series in (
                    trace["actual"],
                    trace["methods"]["GBR_q95"]["predicted"],
                ):
                    require(
                        len(series) == points > 0 and all(map(nonnegative, series)),
                        f"{split_name} {resource} demand series",
                    )
                allocations = trace["methods"]["static"]["allocated"]
                require(
                    len(allocations) == points and all(map(nonnegative, allocations)),
                    f"{split_name} {resource} allocation series",
                )
        static = split["policies"]["static"]
        for key in ("validation_joint_violation_rate", "test_joint_violation_rate"):
            require(0 <= static[key] <= 1, f"{split_name} {key}")
        tasks = static["tasks"]
        require(
            tasks["offered"] == split["offered_tasks"] > 0,
            f"{split_name} offered tasks",
        )
        require(
            tasks["completed"] + tasks["unfinished"] == tasks["offered"]
            and 0 <= tasks["rejected"] <= tasks["unfinished"]
            and math.isclose(
                tasks["completion_rate"], tasks["completed"] / tasks["offered"]
            ),
            f"{split_name} completion accounting",
        )
        response = tasks["timing_seconds"]["response"]
        require(
            response["count"] == tasks["completed"] > 0
            and all(nonnegative(response[key]) for key in ("mean", "median", "p95")),
            f"{split_name} response timing",
        )
        require(
            tasks["throughput_per_second"] > 0
            and tasks["peak_backlog"] >= tasks["final_backlog"] >= 0
            and bool(tasks["timeline"])
            and all(
                nonnegative(point["backlog"])
                and nonnegative(point["throughput_per_second"])
                for point in tasks["timeline"]
            ),
            f"{split_name} throughput and backlog",
        )


def extended_csv() -> bytes:
    """Use the repository's aligned CPU sample with deterministic synthetic memory."""
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(("service_id", "timestamp", "cpu_demand", "memory_demand_gib"))
    with SAMPLE.open(newline="", encoding="utf-8-sig") as source:
        for row in csv.DictReader(source):
            cpu = row["cpu_demand"]
            writer.writerow(
                (row["service_id"], row["timestamp"], cpu, 0.2 + 0.5 * float(cpu))
            )
    return output.getvalue().encode()


def main() -> int:
    backend = _require_env("BACKEND_URL").rstrip("/")
    origin = _require_env("FRONTEND_URL").rstrip("/")
    step = "backend warm-up"
    run_paths: list[str] = []
    failed = False
    with (
        httpx.Client(
            base_url=origin, timeout=90.0, headers={"Origin": origin}
        ) as client,
        httpx.Client(base_url=origin, timeout=90.0) as other,
    ):
        try:
            for path in ("/health", "/ready"):
                expect_status(client.get(backend + path), 200)
            step = "extended limits"
            limits_response = client.get("/api/limits")
            expect_status(limits_response, 200)
            limits = limits_response.json()
            require(
                (
                    limits["extended_max_services"],
                    limits["extended_max_steps"],
                    limits["timeout_seconds"],
                )
                == (4, 600, 42),
                "expected 4 services, 600 steps and a 42-second deadline",
            )
            print(
                "PASS warm-up and extended limits (4 services, 600 steps, 42 s)",
                flush=True,
            )

            def upload(content: bytes) -> httpx.Response:
                return client.post(
                    "/api/simulate/csv",
                    data={"mode": MODE},
                    files={"file": ("extended-sample.csv", content, "text/csv")},
                )

            for label, source in (
                ("synthetic 1", "simulated"),
                ("synthetic 2", "simulated"),
                ("synthetic 3", "simulated"),
                ("extended CSV", "csv"),
            ):
                step = label
                contents = extended_csv() if source == "csv" else None
                started = perf_counter()
                response = (
                    client.post("/api/simulate", json=WORKLOAD)
                    if contents is None
                    else upload(contents)
                )
                latency = perf_counter() - started
                print(
                    f"MEASURE {label} HTTP {response.status_code}, {latency:.3f} s API, "
                    f"{len(response.content)} decoded response bytes",
                    flush=True,
                )
                expect_status(response, 200)
                result = response.json()
                require(result.get("saved") is True, "save could not be confirmed")
                run_id = str(uuid.UUID(result["run_id"]))
                path = f"/api/runs/{run_id}"
                run_paths.append(path)
                check_result(result)
                read_started = perf_counter()
                saved = client.get(path)
                read_latency = perf_counter() - read_started
                expect_status(saved, 200)
                record = saved.json()
                require(
                    record["id"] == run_id
                    and record["source"] == source
                    and record["status"] == "ok"
                    and record["params"]["mode"] == MODE
                    and record["result"]
                    == {
                        key: value
                        for key, value in result.items()
                        if key not in {"saved", "run_id"}
                    },
                    "saved result differs from simulation response",
                )
                require(
                    nonnegative(record["duration_ms"]),
                    "invalid recorded worker duration",
                )
                print(
                    f"PASS {label} metrics and readback ({result['execution_time_seconds']:.3f} s "
                    f"engine, {record['duration_ms']} ms worker, {read_latency:.3f} s readback API)",
                    flush=True,
                )

            step = "history and visitor isolation"
            history = client.get("/api/runs")
            expect_status(history, 200)
            require(
                {path.rsplit("/", 1)[-1] for path in run_paths}
                == {row["id"] for row in history.json()},
                "test visitor history does not contain exactly the four smoke runs",
            )
            expect_status(other.get(run_paths[-1]), 404)
            other_history = other.get("/api/runs")
            expect_status(other_history, 200)
            require(
                other_history.json() == [], "separate visitor has unexpected history"
            )
            print("PASS history and visitor isolation", flush=True)

            for key, limit, setting in (
                ("n_services", 4, "SIM_EXTENDED_MAX_SERVICES"),
                ("n_steps", 600, "SIM_EXTENDED_MAX_STEPS"),
            ):
                step = setting
                excess = client.post("/api/simulate", json={**WORKLOAD, key: limit + 1})
                expect_status(excess, 422)
                require(
                    setting in excess.json()["detail"], "unexpected workload rejection"
                )
            step = "invalid extended CSV"
            invalid = upload(b"service_id,timestamp,cpu_demand\na,0,0.3\n")
            expect_status(invalid, 422)
            require(
                "memory_demand_gib" in invalid.json()["detail"],
                "unexpected CSV rejection",
            )
            print(
                "PASS workload limit enforcement and invalid CSV rejection", flush=True
            )
        except (
            SmokeFailure,
            httpx.RequestError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            # Avoid response bodies, URLs, and exception strings from external data.
            detail = str(exc) if isinstance(exc, SmokeFailure) else type(exc).__name__
            print(f"FAIL {step}: {detail}", flush=True)
            failed = True
        finally:
            for path in run_paths:
                try:
                    expect_status(client.delete(path), 200)
                except (httpx.RequestError, SmokeFailure) as exc:
                    print(f"FAIL smoke-run cleanup: {type(exc).__name__}", flush=True)
                    failed = True
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
