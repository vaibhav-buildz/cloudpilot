"""Exercise persistent worker isolation, equivalence, and failure recovery."""

import asyncio
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

from app import simulation_ipc as ipc
from app.simulation_persistent import PersistentSimulationProcesses
from app.simulation_process import SimulationProcesses
from tests.test_extended import csv_data


async def wait_ready(pool, previous=None):
    async with asyncio.timeout(15):
        while not pool.ready or pool.worker is previous:
            await asyncio.sleep(0.025)
    return pool.worker


async def run(pool, settings, mode="extended-v1", services=3, steps=482, seed=42, csv=None):
    return await pool.run(
        settings,
        mode,
        services,
        steps,
        {"n_services": services, "n_steps": steps, "seed": seed, "target_violation": 0.01},
        csv,
    )


def numerical_result(encoded):
    result = json.loads(encoded)
    result.pop("execution_time_seconds")
    return result


@pytest.mark.anyio
async def test_persistent_worker_matches_fresh_process_and_isolates_jobs(valid_dev_settings):
    settings = valid_dev_settings
    pool = PersistentSimulationProcesses(settings)
    fresh = SimulationProcesses(1)
    pool.start()
    try:
        child = await wait_ready(pool)
        fixtures = [
            ("extended-v1", 3, 482, 42),
            ("cpu-only", 3, 482, 19),
            ("extended-v1", 4, 600, 43),
            ("extended-v1", 3, 482, 42),
        ]
        for mode, services, steps, seed in fixtures:
            expected = await run(fresh, settings, mode, services, steps, seed)
            actual = await run(pool, settings, mode, services, steps, seed)
            assert numerical_result(actual) == numerical_result(expected)
            assert pool.worker is child
        content = csv_data()
        expected = await run(fresh, settings, csv=content)
        assert numerical_result(await run(pool, settings, csv=content)) == numerical_result(
            expected
        )
        with pytest.raises(HTTPException, match="memory_demand_gib") as error:
            await run(pool, settings, csv=b"service_id,timestamp,cpu_demand\na,0,1\n")
        assert error.value.status_code == 422
        assert pool.worker is child
        assert numerical_result(await run(pool, settings)) == numerical_result(
            await run(fresh, settings)
        )
    finally:
        await pool.aclose()
    assert child.poll() is not None


@pytest.mark.anyio
@pytest.mark.parametrize("failure", ["timeout", "cancel", "bad-id", "crash", "recycle"])
async def test_persistent_worker_reaps_before_replacement(valid_dev_settings, monkeypatch, failure):
    settings = valid_dev_settings.model_copy(update={"SIM_WORKER_MAX_JOBS": 1})
    pool = PersistentSimulationProcesses(settings)
    assert not pool.ready
    pool.start()
    try:
        child = await wait_ready(pool)
        entered = asyncio.Event()
        receive = ipc.receive

        async def fail_job(connection, limit):
            if connection is not pool.connection:
                return await receive(connection, limit)
            entered.set()
            if failure == "bad-id":
                _, result = await receive(connection, limit)
                return {"version": ipc.VERSION, "id": "0" * 32, "status": "ok"}, result
            if failure == "crash":
                child.kill()
                return await receive(connection, limit)
            await asyncio.Event().wait()

        if failure != "recycle":
            monkeypatch.setattr(ipc, "receive", fail_job)
        if failure == "timeout":
            deadline = settings.model_copy(update={"SIM_TIMEOUT_SECONDS": 1})
            with pytest.raises(TimeoutError):
                await run(pool, deadline)
        elif failure == "cancel":
            task = asyncio.create_task(run(pool, settings))
            await asyncio.wait_for(entered.wait(), 3)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        elif failure == "bad-id":
            with pytest.raises(ipc.ProtocolError):
                await run(pool, settings)
        elif failure == "crash":
            with pytest.raises((EOFError, ConnectionError)):
                await run(pool, settings)
        else:
            assert numerical_result(await run(pool, settings))["mode"] == "extended-v1"
        assert child.poll() is not None
        monkeypatch.setattr(ipc, "receive", receive)
        replacement = await wait_ready(pool, child)
        assert replacement.poll() is None
        assert (
            numerical_result(await run(pool, valid_dev_settings, seed=23))["parameters"]["seed"]
            == 23
        )
    finally:
        await pool.aclose()


@pytest.mark.anyio
async def test_ipc_rejects_overlong_frames_before_reading_payload():
    left, right = socket.socketpair()
    with left, right:
        left.setblocking(False)
        right.setblocking(False)
        await asyncio.get_running_loop().sock_sendall(
            right, ipc.HEADER.pack(16, 5 * 1024 * 1024 + 1)
        )
        with pytest.raises(ipc.ProtocolError, match="frame length"):
            await asyncio.wait_for(ipc.receive(left, 5 * 1024 * 1024), 1)


def process_running(pid):
    if sys.platform.startswith("linux"):
        try:
            return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[-1].split()[0] != "Z"
        except FileNotFoundError:
            return False
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32")
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x00100000, False, pid)
    if not handle:
        return False
    try:
        return kernel.WaitForSingleObject(handle, 0) == 0x102
    finally:
        kernel.CloseHandle(handle)


@pytest.mark.anyio
@pytest.mark.skipif(not sys.platform.startswith(("win", "linux")), reason="OS parent-death guard")
async def test_worker_exits_if_api_is_killed():
    env = dict(os.environ)
    executable = sys.executable
    if os.name == "nt":
        executable = sys._base_executable
        env["PYTHONPATH"] = os.pathsep.join(os.path.abspath(path) for path in sys.path)
    command = (
        "import asyncio\n"
        "from app.config import Settings\n"
        "from app.simulation_persistent import PersistentSimulationProcesses\n"
        "async def main():\n"
        "    settings = Settings(_env_file=None, APP_ENV='development', DEV_AUTH_DISABLED=True)\n"
        "    pool = PersistentSimulationProcesses(settings)\n"
        "    pool.start()\n"
        "    while not pool.ready: await asyncio.sleep(0.025)\n"
        "    print(pool.worker.pid, flush=True)\n"
        "    await asyncio.Event().wait()\n"
        "asyncio.run(main())\n"
    )
    with subprocess.Popen(
        [executable, "-u", "-c", command],
        stdout=subprocess.PIPE,
        text=True,
        env=env,
    ) as parent:
        try:
            line = await asyncio.wait_for(asyncio.to_thread(parent.stdout.readline), 20)
            worker_pid = int(line)
            assert process_running(worker_pid)
        finally:
            parent.kill()
            parent.wait()
        async with asyncio.timeout(5):
            while process_running(worker_pid):
                await asyncio.sleep(0.025)
