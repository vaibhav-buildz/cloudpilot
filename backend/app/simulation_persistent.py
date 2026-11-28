"""One preloaded simulation process, with bounded IPC and zero waiting jobs."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import socket
import subprocess
import time
import uuid
from collections.abc import Callable

from fastapi import HTTPException

from app import simulation_ipc as ipc
from app.config import Settings
from app.simulation_memory import rss_kib, sample_peak, worker_memory
from app.simulation_process import RETRY_AFTER, SimulationProcesses, simulation_job
from app.workload_limits import MAX_CSV_BYTES

logger = logging.getLogger("cloudpilot")


class PersistentSimulationProcesses(SimulationProcesses):
    def __init__(self, settings: Settings) -> None:
        super().__init__(capacity=1)
        self.settings = settings
        self.worker: subprocess.Popen | None = None
        self.connection: socket.socket | None = None
        self.guard: Callable[[], object] | None = None
        self.supervisor: asyncio.Task | None = None
        self.wake = asyncio.Event()
        self.jobs = 0
        self.peaks: dict[str, int] | None = None

    @property
    def ready(self) -> bool:
        return not self.closed and self.worker is not None and self.worker.poll() is None

    def start(self) -> None:
        self.supervisor = asyncio.create_task(self._supervise())

    async def aclose(self) -> None:
        self.closed = True
        if self.supervisor is not None:
            self.supervisor.cancel()
            await asyncio.gather(self.supervisor, return_exceptions=True)
        self._drop()

    def _drop(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None
        if self.worker is not None:
            self._reap(self.worker)
            self.worker = None
        if self.guard is not None:
            self.guard()
            self.guard = None
        self.wake.set()

    async def _warm(self) -> None:
        started = time.perf_counter()
        nonce = secrets.token_hex(32)
        loop = asyncio.get_running_loop()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            listener.setblocking(False)
            worker = self._spawn(
                self.settings,
                "--persistent",
                str(listener.getsockname()[1]),
                environment={"CLOUDPILOT_WORKER_NONCE": nonce},
            )
            connection = None
            guard = None
            try:
                if os.name == "nt":
                    from app.simulation_windows import attach

                    guard = attach(worker.pid)
                async with asyncio.timeout(self.settings.worker_timeout_seconds):
                    connection, _ = await loop.sock_accept(listener)
                    connection.setblocking(False)
                    message, _ = await ipc.receive(connection, 0)
                imports = message.get("imports_ms")
                if (
                    set(message) != {"version", "status", "nonce", "imports_ms"}
                    or message["status"] != "ready"
                    or message["nonce"] != nonce
                    or type(imports) not in (int, float)
                    or not 0 <= imports <= self.settings.worker_timeout_seconds * 1000
                    or worker.poll() is not None
                ):
                    raise ipc.ProtocolError("Invalid worker readiness message")
                self.worker, self.connection, self.guard = worker, connection, guard
                self.jobs = 0
                logger.info(
                    "Persistent worker ready: startup %.1f ms, imports %.1f ms, memory %s",
                    (time.perf_counter() - started) * 1000,
                    imports,
                    worker_memory(worker.pid),
                )
            except BaseException:
                if connection is not None:
                    connection.close()
                self._reap(worker)
                if guard is not None:
                    guard()
                raise

    def _sample(self) -> None:
        if self.peaks is not None and self.worker is not None:
            sample_peak(self.worker.pid, self.peaks)

    async def _supervise(self) -> None:
        while not self.closed:
            if self.worker is not None and self.worker.poll() is not None and self.peaks is None:
                self._drop()
            if self.worker is None:
                try:
                    await self._warm()
                except Exception as exc:
                    logger.warning("Persistent worker startup failed (%s)", type(exc).__name__)
                    await asyncio.sleep(2)
                    continue
            self._sample()
            try:
                async with asyncio.timeout(0.25 if self.peaks is not None else 0.5):
                    await self.wake.wait()
            except TimeoutError:
                pass
            self.wake.clear()

    async def run(self, settings, mode, max_services, max_steps, parameters, contents) -> bytes:
        if not self.ready or self.connection is None:
            raise HTTPException(503, "Simulation worker is warming up.", RETRY_AFTER)
        connection = self.connection
        job_id = uuid.uuid4().hex
        job = simulation_job(settings, mode, max_services, max_steps, parameters)
        started = time.perf_counter()
        loop = asyncio.get_running_loop()
        deadline = loop.time() + settings.worker_timeout_seconds
        self.peaks = {}
        self._sample()
        self.wake.set()
        try:
            async with asyncio.timeout_at(deadline):
                await ipc.send(
                    connection,
                    {"id": job_id, "job": job, "csv": contents is not None},
                    contents or b"",
                    max_payload=MAX_CSV_BYTES,
                )
                message, payload = await ipc.receive(
                    connection, max(settings.SIM_MAX_RESULT_BYTES, ipc.MAX_ERROR)
                )
            if loop.time() >= deadline:
                raise TimeoutError
            if set(message) != {"version", "id", "status"} or message["id"] != job_id:
                raise ipc.ProtocolError("Response does not belong to the current simulation")
            status = message["status"]
            if status == "timeout" and not payload:
                raise TimeoutError
            if status == "ok":
                if not 0 < len(payload) <= settings.SIM_MAX_RESULT_BYTES:
                    raise ipc.ProtocolError("Unexpected result size")
                try:
                    result = json.loads(payload)
                    if not isinstance(result, dict) or not isinstance(
                        result.get("parameters"), dict
                    ):
                        raise ValueError
                    if payload[-1:] != b"}" or result.get("mode", "cpu-only") != mode:
                        raise ValueError
                except (ValueError, RecursionError) as exc:
                    raise ipc.ProtocolError("Invalid simulation result") from exc
            elif status == "invalid" and 0 < len(payload) <= ipc.MAX_ERROR:
                error = payload.decode()
            elif status == "too-large" and not payload:
                error = "Simulation output exceeds the size limit. Use a smaller workload."
            else:
                raise ipc.ProtocolError("Invalid simulation response status")
            if loop.time() >= deadline:
                raise TimeoutError
        except BaseException:
            # No await before reaping. Cancellation cannot release the admission slot early.
            self._drop()
            raise
        finally:
            self._sample()
            logger.info(
                "Persistent worker job: mode %s, duration %.1f ms, memory peaks %s",
                mode,
                (time.perf_counter() - started) * 1000,
                self.peaks,
            )
            self.peaks = None
        self.jobs += 1
        if self.jobs >= settings.SIM_WORKER_MAX_JOBS or (
            self.worker is not None
            and rss_kib(self.worker.pid) >= settings.SIM_WORKER_RECYCLE_RSS_MIB * 1024
        ):
            self._drop()
        if status != "ok":
            raise HTTPException(422, error)
        return payload
