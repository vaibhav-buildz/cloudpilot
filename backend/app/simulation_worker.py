"""One web simulation per process. The offline study uses the engine directly."""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path


class InvalidWorkload(ValueError):
    """CSV data failed input validation."""


def execute(job: dict, csv_path: Path | None, profile: dict | None = None) -> dict:
    started = time.perf_counter()
    from threadpoolctl import threadpool_limits

    from app.engine.csv_loader import load_workload_from_csv
    from app.engine.extended import parse_extended_csv, run_extended
    from app.engine.runner import run_experiment

    imported = time.perf_counter()
    if profile is not None:
        profile["imports_ms"] = round((imported - started) * 1000, 1)

    with threadpool_limits(limits=job["native_threads"]):
        extended = job["mode"] == "extended-v1"
        kwargs = job["parameters"]
        if csv_path is not None:
            content = csv_path.read_bytes()
            try:
                workload = (
                    parse_extended_csv(content) if extended else load_workload_from_csv(content)
                )
            except ValueError as exc:
                raise InvalidWorkload(str(exc)) from exc
            services, steps = (workload[0] if extended else workload.demand).shape
            for name, value, cap in (
                ("services", services, job["max_services"]),
                ("time steps", steps, job["max_steps"]),
            ):
                if value > cap:
                    raise InvalidWorkload(
                        f"CSV contains {value} {name}, exceeding the limit of {cap}."
                    )
            kwargs = {**kwargs, "workload": workload, "n_services": services, "n_steps": steps}

        if profile is not None:
            profile["setup_ms"] = round((time.perf_counter() - imported) * 1000, 1)

        if extended:
            fit_seconds: dict[str, float] | None = {} if profile is not None else None
            result = run_extended(**kwargs, rf_jobs=job["rf_jobs"], fit_seconds=fit_seconds)
            if fit_seconds is not None:
                profile["fit_ms"] = {
                    name: round(seconds * 1000, 1) for name, seconds in fit_seconds.items()
                }
        else:
            result = run_experiment(**kwargs, rf_jobs=job["rf_jobs"], include_diagnostics=True)

        if profile is not None:
            profile["engine_ms"] = round(result["execution_time_seconds"] * 1000)
        return result


def exit_on_parent_death(parent_pid: int) -> None:
    if os.name == "nt":
        import ctypes

        kernel = ctypes.windll.kernel32
        kernel.OpenProcess.restype = ctypes.c_void_p
        handle = kernel.OpenProcess(0x00100000, False, parent_pid)  # SYNCHRONIZE
        if handle:
            kernel.WaitForSingleObject(ctypes.c_void_p(handle), ctypes.c_ulong(0xFFFFFFFF))
            kernel.CloseHandle(ctypes.c_void_p(handle))
    else:
        os.read(0, 1)
    os._exit(1)


def main(directory: Path, parent_pid: int) -> int:
    if sys.platform.startswith("linux"):
        import ctypes
        import signal

        # PR_SET_PDEATHSIG also works when native code is holding the GIL.
        if ctypes.CDLL(None).prctl(1, signal.SIGKILL, 0, 0, 0) == 0:
            if os.getppid() != parent_pid:
                return 1
        else:
            threading.Thread(target=exit_on_parent_death, args=(parent_pid,), daemon=True).start()
    else:
        threading.Thread(target=exit_on_parent_death, args=(parent_pid,), daemon=True).start()
    job = json.loads((directory / "job.json").read_bytes())
    csv_path = directory / "input.csv"
    profile = {}
    try:
        result = execute(job, csv_path if csv_path.exists() else None, profile)
    except TimeoutError:
        return 2
    except InvalidWorkload as exc:
        (directory / "error.txt").write_text(str(exc)[:1000], encoding="utf-8")
        return 3

    encoding_started = time.perf_counter()
    encoded = json.dumps(
        result, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode()
    if len(encoded) > job["max_result_bytes"]:
        return 4
    (directory / "result.json").write_bytes(encoded)
    profile["encode_ms"] = round((time.perf_counter() - encoding_started) * 1000, 1)
    if sys.platform.startswith("linux"):
        import resource

        profile["peak_worker_rss_kib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    print(
        json.dumps({"event": "simulation_worker_profile", "mode": job["mode"], **profile}),
        file=sys.stderr,
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]), int(sys.argv[2])))
