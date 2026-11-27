"""Exercise real child process lifecycles with controlled local requests."""

import asyncio
import json
import subprocess

import httpx
import pytest
from fastapi.testclient import TestClient
from threadpoolctl import threadpool_info

from app.main import create_app
from app.simulation_worker import execute
from tests.conftest import TEST_VALID_KEY

PAYLOAD = {"n_services": 3, "n_steps": 482}
HEADERS = {
    "X-API-Key": TEST_VALID_KEY,
    "X-Visitor-Id": "11111111-1111-4111-8111-111111111111",
}


@pytest.fixture
def sleepers(monkeypatch):
    """Replace only the spawned command, using a real OS process and handle."""
    popen = subprocess.Popen
    started = asyncio.Event()
    children = []

    def spawn(command, **kwargs):
        child = popen([command[0], "-c", "import time; time.sleep(60)"], **kwargs)
        children.append(child)
        started.set()
        return child

    monkeypatch.setattr("app.simulation_process.subprocess.Popen", spawn)
    yield started, children
    for child in children:
        if child.poll() is None:
            child.kill()
            child.wait()
            pytest.fail("A simulation worker survived its request")


@pytest.mark.anyio
async def test_busy_timeout_reaps_worker_before_readmission(valid_dev_settings, sleepers):
    settings = valid_dev_settings.model_copy(update={"SIM_TIMEOUT_SECONDS": 1})
    app = create_app(settings)
    started, children = sleepers
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://localhost"
    ) as client:
        admitted = asyncio.create_task(client.post("/api/simulate", json=PAYLOAD, headers=HEADERS))
        await asyncio.wait_for(started.wait(), 5)
        same = await client.post("/api/simulate", json=PAYLOAD, headers=HEADERS)
        assert same.status_code == 429 and same.headers["Retry-After"] == "5"
        other_headers = HEADERS | {"X-Visitor-Id": "22222222-2222-4222-8222-222222222222"}
        busy = await asyncio.gather(
            *(client.post("/api/simulate", json=PAYLOAD, headers=other_headers) for _ in range(5))
        )
        assert all(
            response.status_code == 503 and response.headers["Retry-After"] == "5"
            for response in busy
        )
        assert len(children) == 1 and children[0].poll() is None
        assert (await admitted).status_code == 504
        assert children[0].poll() is not None
        assert not app.state.simulations.active and not app.state.simulations.workers
        assert (
            await client.post("/api/simulate", json=PAYLOAD, headers=other_headers)
        ).status_code == 504
        assert len(children) == 2 and children[1].poll() is not None


@pytest.mark.anyio
@pytest.mark.parametrize("cancel", [False, True])
async def test_client_disconnect_or_handler_cancellation_reaps_worker(
    valid_dev_settings, sleepers, cancel
):
    app = create_app(valid_dev_settings)
    started, children = sleepers
    incoming = asyncio.Queue()
    incoming.put_nowait({"type": "http.request", "body": json.dumps(PAYLOAD).encode()})
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/simulate",
        "scheme": "http",
        "query_string": b"",
        "client": ("127.0.0.1", 1),
        "headers": [(b"content-type", b"application/json")]
        + [(key.lower().encode(), value.encode()) for key, value in HEADERS.items()],
    }

    async def send(message):
        pass

    handling = asyncio.create_task(app(scope, incoming.get, send))
    await asyncio.wait_for(started.wait(), 5)
    if cancel:
        handling.cancel()
        with pytest.raises(asyncio.CancelledError):
            await handling
    else:
        incoming.put_nowait({"type": "http.disconnect"})
        await asyncio.wait_for(handling, timeout=3)
    assert children[0].poll() is not None
    assert not app.state.simulations.active and not app.state.simulations.workers


def test_worker_enforces_output_limit(valid_dev_settings):
    settings = valid_dev_settings.model_copy(update={"SIM_MAX_RESULT_BYTES": 256})
    with TestClient(create_app(settings)) as client:
        response = client.post("/api/simulate", json=PAYLOAD, headers=HEADERS)
    assert response.status_code == 422
    assert "output exceeds" in response.json()["detail"]


def test_worker_execution_profile_limits_model_and_native_threads(monkeypatch):
    def inspect(rf_jobs, **kwargs):
        pools = threadpool_info()
        assert pools and all(pool["num_threads"] == 1 for pool in pools)
        assert rf_jobs == 2
        return {}

    monkeypatch.setattr("app.engine.runner.run_experiment", inspect)
    assert (
        execute({"mode": "cpu-only", "parameters": {}, "rf_jobs": 2, "native_threads": 1}, None)
        == {}
    )
