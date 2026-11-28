"""Bounded admission and lifecycle management for web simulation workers."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock

from fastapi import HTTPException

from app.config import Settings
from app.simulation_memory import sample_peak, worker_memory

RETRY_AFTER = {"Retry-After": "5"}
logger = logging.getLogger("cloudpilot")


def simulation_job(
    settings: Settings, mode: str, services: int, steps: int, parameters: dict
) -> dict:
    return {
        "mode": mode,
        "parameters": {**parameters, "timeout_seconds": settings.worker_timeout_seconds},
        "rf_jobs": settings.SIM_RF_JOBS,
        "native_threads": settings.SIM_NATIVE_THREADS,
        "max_services": services,
        "max_steps": steps,
        "max_result_bytes": settings.SIM_MAX_RESULT_BYTES,
    }


class SimulationProcesses:
    """One gate per server process, with immediate rejection and zero queue slots."""

    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self.active: set[str] = set()
        self.workers: set[subprocess.Popen] = set()
        self.lock = Lock()
        self.closed = False

    @property
    def ready(self) -> bool:
        return not self.closed

    def start(self) -> None:
        pass

    async def aclose(self) -> None:
        self.close()

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

    @staticmethod
    def _spawn(settings: Settings, *args: str, environment: dict | None = None):
        native = str(settings.SIM_NATIVE_THREADS)
        env = {
            key: value
            for key, value in os.environ.items()
            if not any(word in key.upper() for word in ("SECRET", "TOKEN", "PASSWORD", "API_KEY"))
        }
        env.update(
            OPENBLAS_NUM_THREADS=native,
            OMP_NUM_THREADS=native,
            MKL_NUM_THREADS=native,
            BLIS_NUM_THREADS=native,
        )
        env.update(environment or {})
        executable = sys.executable
        if os.name == "nt" and sys._base_executable != executable:
            # The venv redirector would leave the API holding the wrong child handle.
            executable = sys._base_executable
            env["PYTHONPATH"] = os.pathsep.join(os.path.abspath(path) for path in sys.path)
        return subprocess.Popen(
            [executable, "-m", "app.simulation_worker", *args, str(os.getpid())],
            stdin=subprocess.DEVNULL if os.name == "nt" else subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            env=env,
        )

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
                json.dumps(simulation_job(settings, mode, max_services, max_steps, parameters)),
                encoding="utf-8",
            )
            if contents is not None:
                (directory / "input.csv").write_bytes(contents)
            with self.lock:
                if self.closed:
                    raise HTTPException(503, "Simulation service is restarting.", RETRY_AFTER)
                if loop.time() >= deadline:
                    raise TimeoutError
                idle = worker_memory()
                worker = self._spawn(settings, temporary)
                self.workers.add(worker)
            peaks = {}
            next_sample = loop.time()
            try:
                async with asyncio.timeout_at(deadline):
                    while worker.poll() is None:
                        if loop.time() >= next_sample:
                            sample_peak(worker.pid, peaks)
                            next_sample = loop.time() + 0.25
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
                if idle:
                    logger.info(
                        "Per-request worker job: mode %s, idle %s, memory peaks %s",
                        mode,
                        idle,
                        peaks,
                    )
