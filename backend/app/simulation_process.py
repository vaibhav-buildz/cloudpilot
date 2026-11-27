"""Bounded admission and lifecycle management for web simulation workers."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock

from fastapi import HTTPException

from app.config import Settings

RETRY_AFTER = {"Retry-After": "5"}


class SimulationProcesses:
    """One gate per server process, with immediate rejection and zero queue slots."""

    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self.active: set[str] = set()
        self.workers: set[subprocess.Popen] = set()
        self.lock = Lock()
        self.closed = False

    @contextmanager
    def admit(self, visitor: str):
        with self.lock:
            if visitor in self.active:
                raise HTTPException(
                    429, "A simulation is already active for this visitor.", RETRY_AFTER
                )
            if self.closed or len(self.active) >= self.capacity:
                raise HTTPException(503, "All simulation slots are busy.", RETRY_AFTER)
            self.active.add(visitor)
        try:
            yield
        finally:
            with self.lock:
                self.active.remove(visitor)

    @staticmethod
    def _reap(worker: subprocess.Popen) -> None:
        try:
            if worker.poll() is None:
                worker.kill()
        except ProcessLookupError:
            pass
        finally:
            worker.wait()
            if worker.stdin is not None:
                worker.stdin.close()

    def close(self) -> None:
        with self.lock:
            self.closed = True
            for worker in self.workers:
                self._reap(worker)

    async def run(
        self,
        settings: Settings,
        mode: str,
        max_services: int,
        max_steps: int,
        parameters: dict,
        contents: bytes | None,
    ) -> bytes:
        timeout = settings.worker_timeout_seconds
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        with TemporaryDirectory(prefix="cloudpilot-simulation-") as temporary:
            directory = Path(temporary)
            (directory / "job.json").write_text(
                json.dumps(
                    {
                        "mode": mode,
                        "parameters": {**parameters, "timeout_seconds": timeout},
                        "rf_jobs": settings.SIM_RF_JOBS,
                        "native_threads": settings.SIM_NATIVE_THREADS,
                        "max_services": max_services,
                        "max_steps": max_steps,
                        "max_result_bytes": settings.SIM_MAX_RESULT_BYTES,
                    }
                ),
                encoding="utf-8",
            )
            if contents is not None:
                (directory / "input.csv").write_bytes(contents)
            native = str(settings.SIM_NATIVE_THREADS)
            env = {
                **os.environ,
                "OPENBLAS_NUM_THREADS": native,
                "OMP_NUM_THREADS": native,
                "MKL_NUM_THREADS": native,
                "BLIS_NUM_THREADS": native,
            }
            executable = sys.executable
            if os.name == "nt" and sys._base_executable != executable:
                # The venv redirector starts another process on Windows. Open the
                # real interpreter so the handle always identifies the engine.
                executable = sys._base_executable
                env["PYTHONPATH"] = os.pathsep.join(os.path.abspath(path) for path in sys.path)
            with self.lock:
                if self.closed:
                    raise HTTPException(503, "Simulation service is restarting.", RETRY_AFTER)
                if loop.time() >= deadline:
                    raise TimeoutError
                worker = subprocess.Popen(
                    [executable, "-m", "app.simulation_worker", temporary, str(os.getpid())],
                    stdin=subprocess.DEVNULL if os.name == "nt" else subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    env=env,
                )
                self.workers.add(worker)
            try:
                async with asyncio.timeout_at(deadline):
                    while worker.poll() is None:
                        await asyncio.sleep(0.025)
                if loop.time() >= deadline:
                    raise TimeoutError
                if worker.returncode == 2:
                    raise TimeoutError
                if worker.returncode == 3:
                    detail = (directory / "error.txt").read_text(encoding="utf-8")
                    raise HTTPException(422, detail)
                if worker.returncode == 4:
                    raise HTTPException(
                        422, "Simulation output exceeds the size limit. Use a smaller workload."
                    )
                if worker.returncode != 0:
                    raise RuntimeError(f"Simulation worker exited with status {worker.returncode}")
                return (directory / "result.json").read_bytes()
            finally:
                # No await between terminating the worker, reaping it and releasing capacity.
                with self.lock:
                    self._reap(worker)
                    self.workers.remove(worker)
