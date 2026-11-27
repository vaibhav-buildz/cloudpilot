"""One web simulation per process. The offline study uses the engine directly."""

from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path


class InvalidWorkload(ValueError):
    """CSV data failed input validation."""


def execute(job: dict, csv_path: Path | None) -> dict:
    from threadpoolctl import threadpool_limits

    from app.engine.csv_loader import load_workload_from_csv
    from app.engine.extended import parse_extended_csv, run_extended
    from app.engine.runner import run_experiment

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

        options = {"include_diagnostics": True} if not extended else {}
        run = run_extended if extended else run_experiment
        return run(**kwargs, **options, rf_jobs=job["rf_jobs"])


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
    try:
        result = execute(job, csv_path if csv_path.exists() else None)
    except TimeoutError:
        return 2
    except InvalidWorkload as exc:
        (directory / "error.txt").write_text(str(exc)[:1000], encoding="utf-8")
        return 3

    encoded = json.dumps(
        result, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode()
    if len(encoded) > job["max_result_bytes"]:
        return 4
    (directory / "result.json").write_bytes(encoded)
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]), int(sys.argv[2])))
