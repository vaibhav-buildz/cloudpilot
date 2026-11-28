"""One web simulation per process. The offline study uses the engine directly."""

from __future__ import annotations

import asyncio
import json
import os
import socket
import sys
import threading
import time
from pathlib import Path

from app import simulation_ipc as ipc
from app.workload_limits import MAX_CSV_BYTES


class InvalidWorkload(ValueError):
    """CSV data failed input validation."""


def dependencies():
    from threadpoolctl import threadpool_limits

    from app.engine.csv_loader import load_workload_from_csv
    from app.engine.extended import parse_extended_csv, run_extended
    from app.engine.runner import run_experiment

    return (
        threadpool_limits,
        load_workload_from_csv,
        parse_extended_csv,
        run_extended,
        run_experiment,
    )


def execute(job: dict, csv_path: Path | None, profile: dict | None = None) -> dict:
    # Keep the per-request worker and its tests on the same execution path.
    return execute_workload(job, csv_path.read_bytes() if csv_path is not None else None, profile)


def execute_workload(job: dict, content: bytes | None, profile: dict | None = None) -> dict:
    started = time.perf_counter()
    threadpool_limits, load_workload_from_csv, parse_extended_csv, run_extended, run_experiment = (
        dependencies()
    )
    imported = time.perf_counter()
    if profile is not None:
        profile["imports_ms"] = round((imported - started) * 1000, 1)

    with threadpool_limits(limits=job["native_threads"]):
        extended = job["mode"] == "extended-v1"
        kwargs = job["parameters"]
        if content is not None:
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
            schedule_seconds = [] if profile is not None else None
            result = run_extended(
                **kwargs,
                rf_jobs=job["rf_jobs"],
                fit_seconds=fit_seconds,
                schedule_seconds=schedule_seconds,
            )
            if fit_seconds is not None:
                profile["fit_ms"] = {
                    name: round(seconds * 1000, 1) for name, seconds in fit_seconds.items()
                }
                profile["schedule_ms"] = round(sum(schedule_seconds) * 1000, 1)
        else:
            result = run_experiment(**kwargs, rf_jobs=job["rf_jobs"], include_diagnostics=True)

        if profile is not None:
            profile["engine_ms"] = round(result["execution_time_seconds"] * 1000)
        return result


def exit_on_parent_death() -> None:
    os.read(0, 1)
    os._exit(1)


def watch_parent(parent_pid: int) -> None:
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        if os.getppid() != parent_pid:
            os._exit(1)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x00100000, False, parent_pid)  # SYNCHRONIZE
        if not handle:
            os._exit(1)
        if kernel.WaitForSingleObject(handle, 0) != 0x102:  # WAIT_TIMEOUT
            os._exit(1)

        def wait() -> None:
            kernel.WaitForSingleObject(handle, 0xFFFFFFFF)
            kernel.CloseHandle(handle)
            os._exit(1)

        threading.Thread(target=wait, daemon=True).start()
        return
    if sys.platform.startswith("linux"):
        import ctypes
        import signal

        # PR_SET_PDEATHSIG also works when native code is holding the GIL.
        if ctypes.CDLL(None).prctl(1, signal.SIGKILL, 0, 0, 0) == 0:
            if os.getppid() != parent_pid:
                os._exit(1)
            return
    threading.Thread(target=exit_on_parent_death, daemon=True).start()


def encode(result: dict) -> bytes:
    return json.dumps(result, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


def log_profile(mode: str, profile: dict) -> None:
    if sys.platform.startswith("linux"):
        import resource

        profile["peak_worker_rss_kib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    print(
        json.dumps({"event": "simulation_worker_profile", "mode": mode, **profile}),
        file=sys.stderr,
        flush=True,
    )


async def serve_job(connection: socket.socket, message: dict, content: bytes) -> None:
    job_id = message.get("id")
    is_csv = message.get("csv")
    if (
        set(message) != {"version", "id", "job", "csv"}
        or not isinstance(job_id, str)
        or not ipc.JOB_ID.fullmatch(job_id)
        or type(is_csv) is not bool
        or (content and not is_csv)
        or not isinstance(message["job"], dict)
    ):
        raise ipc.ProtocolError("Invalid simulation request")
    job = message["job"]
    limit = job.get("max_result_bytes")
    if (
        job.get("mode") not in ("cpu-only", "extended-v1")
        or type(limit) is not int
        or not 1 <= limit <= 4_000_000
    ):
        raise ipc.ProtocolError("Invalid simulation job limits")
    profile = {}
    try:
        result = execute_workload(job, content if is_csv else None, profile)
    except InvalidWorkload as exc:
        await ipc.send(
            connection,
            {"id": job_id, "status": "invalid"},
            str(exc)[:1000].encode(),
            max_payload=ipc.MAX_ERROR,
        )
        return
    except TimeoutError:
        await ipc.send(connection, {"id": job_id, "status": "timeout"}, max_payload=0)
        return
    started = time.perf_counter()
    encoded = encode(result)
    profile["encode_ms"] = round((time.perf_counter() - started) * 1000, 1)
    log_profile(job["mode"], profile)
    if len(encoded) > limit:
        await ipc.send(connection, {"id": job_id, "status": "too-large"}, max_payload=0)
        return
    await ipc.send(connection, {"id": job_id, "status": "ok"}, encoded, max_payload=limit)


async def serve(address: int, inherited: bool = False) -> None:
    nonce = os.environ.pop("CLOUDPILOT_WORKER_NONCE")
    connection = (
        socket.socket(fileno=address)
        if inherited
        else socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    )
    with connection:
        connection.setblocking(False)
        if not inherited:
            await asyncio.get_running_loop().sock_connect(connection, ("127.0.0.1", address))
        started = time.perf_counter()
        dependencies()
        imports_ms = round((time.perf_counter() - started) * 1000, 1)
        await ipc.send(
            connection,
            {"status": "ready", "nonce": nonce, "imports_ms": imports_ms},
            max_payload=0,
        )
        while True:
            await serve_job(connection, *await ipc.receive(connection, MAX_CSV_BYTES))


def main(directory: Path) -> int:
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
    encoded = encode(result)
    if len(encoded) > job["max_result_bytes"]:
        return 4
    (directory / "result.json").write_bytes(encoded)
    profile["encode_ms"] = round((time.perf_counter() - encoding_started) * 1000, 1)
    log_profile(job["mode"], profile)
    return 0


if __name__ == "__main__":
    watch_parent(int(sys.argv[-1]))
    if sys.argv[1] in ("--persistent", "--persistent-fd"):
        try:
            asyncio.run(serve(int(sys.argv[2]), inherited=sys.argv[1] == "--persistent-fd"))
        except (EOFError, ConnectionError):
            sys.exit(1)
        except Exception as exc:
            # Exceptions may include CSV contents. Log only their type.
            print(f"Persistent worker failed ({type(exc).__name__})", file=sys.stderr, flush=True)
            sys.exit(1)
    else:
        sys.exit(main(Path(sys.argv[1])))
