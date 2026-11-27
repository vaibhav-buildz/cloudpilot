"""Tests for database persistence layer, PostgREST repository, and /api/runs endpoints."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db.repository import (
    InMemoryRunRepository,
    SupabaseRunRepository,
)
from app.main import create_app
from tests.conftest import mock_simulation

KEY_A = "a" * 32
KEY_B = "b" * 32
SECRET_KEY = "super-secret-service-role-key-999"


def test_migration_sql_contains_security_controls() -> None:
    """Verify migration SQL explicitly enables RLS and revokes access from public roles."""
    migration_path = (
        Path(__file__).resolve().parent.parent.parent
        / "supabase"
        / "migrations"
        / "0001_simulation_runs.sql"
    )
    assert migration_path.exists(), f"Migration file not found at {migration_path}"
    content = migration_path.read_text(encoding="utf-8").lower()

    assert "enable row level security" in content
    assert "revoke all on table public.simulation_runs from anon, authenticated" in content


@pytest.mark.anyio
async def test_in_memory_repository_crud_and_prune() -> None:
    """Verify full CRUD and pruning lifecycle on InMemoryRunRepository."""
    repo = InMemoryRunRepository()

    # Save runs for client 1
    run1 = await repo.save_run(
        client_id="client_1",
        source="simulated",
        params={"seed": 42},
        status="ok",
        result={"savings": 0.55},
        duration_ms=120,
    )
    assert run1["id"] is not None
    assert run1["client_id"] == "client_1"

    # Save run for client 2
    run2 = await repo.save_run(
        client_id="client_2",
        source="csv",
        params={"n_services": 10},
        status="ok",
        result={"savings": 0.40},
        duration_ms=250,
    )

    # Scoping check: list_runs
    c1_runs = await repo.list_runs("client_1")
    assert len(c1_runs) == 1
    assert c1_runs[0]["id"] == run1["id"]

    c2_runs = await repo.list_runs("client_2")
    assert len(c2_runs) == 1
    assert c2_runs[0]["id"] == run2["id"]

    # Scoping check: get_run
    assert await repo.get_run("client_1", run1["id"]) is not None
    assert await repo.get_run("client_1", run2["id"]) is None  # Cannot see client 2
    assert await repo.get_run("client_2", run1["id"]) is None  # Cannot see client 1

    # Scoping check: delete_run
    assert await repo.delete_run("client_1", run2["id"]) is False  # Cannot delete client 2
    assert await repo.delete_run("client_1", run1["id"]) is True
    assert await repo.get_run("client_1", run1["id"]) is None

    # Test pruning beyond keep=50
    for i in range(55):
        await repo.save_run(
            client_id="prune_client",
            source="simulated",
            params={"idx": i},
            status="ok",
        )

    all_prune = await repo.list_runs("prune_client", limit=100)
    assert len(all_prune) == 55

    pruned_count = await repo.prune("prune_client", keep=50)
    assert pruned_count == 5

    remaining = await repo.list_runs("prune_client", limit=100)
    assert len(remaining) == 50


@pytest.mark.anyio
async def test_supabase_repository_mock_transport_crud() -> None:
    """Verify SupabaseRunRepository HTTP calls, headers, query params, and payloads."""
    recorded_requests: list[httpx.Request] = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)
        url_str = str(request.url)

        # Check headers never leak keys in places they shouldn't
        assert request.headers.get("apikey") == SECRET_KEY
        assert request.headers.get("Authorization") == f"Bearer {SECRET_KEY}"

        if request.method == "POST" and "/simulation_runs" in url_str:
            data = json.loads(request.read())
            record = {
                "id": "11111111-1111-1111-1111-111111111111",
                "created_at": "2026-11-24T00:00:00Z",
                **data,
            }
            return httpx.Response(201, json=[record])

        if request.method == "GET" and "/simulation_runs" in url_str:
            if "select=id" in url_str:
                return httpx.Response(200, json=[{"id": "excess-1"}])
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "11111111-1111-1111-1111-111111111111",
                        "client_id": "client_a",
                        "source": "simulated",
                        "status": "ok",
                    }
                ],
            )

        if request.method == "DELETE" and "/simulation_runs" in url_str:
            return httpx.Response(200, json=[{"id": "11111111-1111-1111-1111-111111111111"}])

        return httpx.Response(404, json={"detail": "Not found"})

    transport = httpx.MockTransport(mock_handler)
    client = httpx.AsyncClient(
        base_url="https://mock.supabase.co/rest/v1",
        headers={
            "apikey": SECRET_KEY,
            "Authorization": f"Bearer {SECRET_KEY}",
            "Content-Type": "application/json",
        },
        transport=transport,
    )
    repo = SupabaseRunRepository(
        supabase_url="https://mock.supabase.co",
        supabase_service_key=SECRET_KEY,
        client=client,
    )

    # Save
    saved = await repo.save_run(
        client_id="client_a",
        source="simulated",
        params={"seed": 42},
        status="ok",
    )
    assert saved["id"] == json.loads(recorded_requests[-1].content)["id"]
    assert recorded_requests[-1].method == "POST"

    # List
    items = await repo.list_runs("client_a", limit=20, offset=0)
    assert len(items) == 1
    assert "client_id=eq.client_a" in str(recorded_requests[-1].url)
    assert "limit=20" in str(recorded_requests[-1].url)

    # Get
    item = await repo.get_run("client_a", "11111111-1111-1111-1111-111111111111")
    assert item is not None
    assert "id=eq.11111111-1111-1111-1111-111111111111" in str(recorded_requests[-1].url)

    # Delete
    deleted = await repo.delete_run("client_a", "11111111-1111-1111-1111-111111111111")
    assert deleted is True

    # Prune
    pruned = await repo.prune("client_a", keep=50)
    assert pruned == 1


@pytest.mark.anyio
async def test_supabase_repository_retry_on_500() -> None:
    """Verify SupabaseRunRepository retries once on 5xx error and recovers."""
    call_count = 0

    def mock_retry_handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(500, text="Internal Server Error")
        return httpx.Response(200, json=[{"id": "run-ok"}])

    transport = httpx.MockTransport(mock_retry_handler)
    client = httpx.AsyncClient(
        base_url="https://mock.supabase.co/rest/v1",
        headers={
            "apikey": SECRET_KEY,
            "Authorization": f"Bearer {SECRET_KEY}",
            "Content-Type": "application/json",
        },
        transport=transport,
    )
    repo = SupabaseRunRepository(
        supabase_url="https://mock.supabase.co",
        supabase_service_key=SECRET_KEY,
        client=client,
    )

    items = await repo.list_runs("client_a")
    assert len(items) == 1
    assert call_count == 2  # Proves retry occurred


@pytest.mark.anyio
async def test_save_replays_same_insert_id_after_lost_commit_response():
    writes = []
    stored = {}

    def handler(request):
        if request.method == "POST":
            record = json.loads(request.content)
            writes.append(record["id"])
            assert request.url.params["on_conflict"] == "id"
            assert "resolution=ignore-duplicates" in request.headers["Prefer"]
            if record["id"] not in stored:
                stored[record["id"]] = record
                raise httpx.ReadTimeout("response lost after commit", request=request)
            return httpx.Response(201, json=[])
        assert request.url.params["client_id"] == "eq.visitor"
        assert request.url.params["id"] == f"eq.{writes[0]}"
        assert "result" not in request.url.params["select"]
        return httpx.Response(200, json=[{"id": writes[0]}])

    async with httpx.AsyncClient(
        base_url="https://mock.supabase.co", transport=httpx.MockTransport(handler)
    ) as client:
        repo = SupabaseRunRepository("https://mock.supabase.co", SECRET_KEY, client)
        result = await repo.save_run("visitor", "simulated", {}, "ok", result={"data": 1})
    assert len(writes) == 2 and len(stored) == 1
    assert result["id"] == writes[0] == writes[1]


def test_saved_run_survives_prune_failure(client):
    with (
        mock_simulation({"time_split": {}}),
        patch.object(client.app.state.repo, "prune", side_effect=RuntimeError),
    ):
        headers = {"X-API-Key": KEY_A}
        settings = client.app.state.settings
        headers["X-API-Key"] = settings.CLOUDPILOT_API_KEY
        response = client.post("/api/simulate", json={}, headers=headers)
        result = response.json()
        assert result["saved"]
        summaries = client.get("/api/runs", headers=headers).json()
        assert summaries[0]["id"] == result["run_id"] and summaries[0]["result"] is None
        detail = client.get(f"/api/runs/{result['run_id']}", headers=headers).json()
        assert detail["result"]["time_split"] == {}


@pytest.mark.anyio
async def test_supabase_repository_no_secret_leakage_on_failure() -> None:
    """Verify service key is never leaked in exception messages."""

    def mock_failing_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="Service Unavailable")

    transport = httpx.MockTransport(mock_failing_handler)
    client = httpx.AsyncClient(
        base_url="https://mock.supabase.co/rest/v1",
        headers={
            "apikey": SECRET_KEY,
            "Authorization": f"Bearer {SECRET_KEY}",
            "Content-Type": "application/json",
        },
        transport=transport,
    )
    repo = SupabaseRunRepository(
        supabase_url="https://mock.supabase.co",
        supabase_service_key=SECRET_KEY,
        client=client,
    )

    with pytest.raises(RuntimeError) as exc_info:
        await repo.save_run("client_a", "simulated", {}, "ok")

    assert SECRET_KEY not in str(exc_info.value)


def test_runs_endpoints_scoping_and_uuid_validation() -> None:
    """Verify /api/runs endpoints enforce client scoping and UUID validation."""
    settings = Settings(
        APP_ENV="development",
        CLOUDPILOT_API_KEY=KEY_A,
        ALLOWED_ORIGIN="http://localhost:5173",
        DEV_AUTH_DISABLED=False,
    )
    app = create_app(settings)
    client = TestClient(app)

    repo: InMemoryRunRepository = app.state.repo

    # Seed run for Client A and Client B
    from app.security import hash_client_key

    client_a_id = hash_client_key(KEY_A)
    client_b_id = hash_client_key(KEY_B)

    # We manually populate repo
    run_a = TestClient(app).app.state.loop = None
    import asyncio

    run_a = asyncio.run(
        repo.save_run(
            client_id=client_a_id,
            source="simulated",
            params={"seed": 1},
            status="ok",
            result={"savings": 0.5},
        )
    )
    run_b = asyncio.run(
        repo.save_run(
            client_id=client_b_id,
            source="simulated",
            params={"seed": 2},
            status="ok",
            result={"savings": 0.6},
        )
    )

    # 1. UUID validation: invalid UUID returns 422
    res_invalid = client.get("/api/runs/not-a-valid-uuid", headers={"X-API-Key": KEY_A})
    assert res_invalid.status_code == 422
    assert "UUID" in res_invalid.json()["detail"]

    res_del_invalid = client.delete("/api/runs/not-a-valid-uuid", headers={"X-API-Key": KEY_A})
    assert res_del_invalid.status_code == 422

    # 2. Scoping: Client A list only sees run_a
    res_list = client.get("/api/runs", headers={"X-API-Key": KEY_A})
    assert res_list.status_code == 200
    runs = res_list.json()
    assert len(runs) == 1
    assert runs[0]["id"] == run_a["id"]

    # 3. Scoping: Client A fetching Client B's run returns 404
    res_get_b = client.get(f"/api/runs/{run_b['id']}", headers={"X-API-Key": KEY_A})
    assert res_get_b.status_code == 404

    # 4. Scoping: Client A deleting Client B's run returns 404
    res_del_b = client.delete(f"/api/runs/{run_b['id']}", headers={"X-API-Key": KEY_A})
    assert res_del_b.status_code == 404

    # 5. Client A fetching own run succeeds
    res_get_a = client.get(f"/api/runs/{run_a['id']}", headers={"X-API-Key": KEY_A})
    assert res_get_a.status_code == 200
    assert res_get_a.json()["id"] == run_a["id"]

    # 6. Client A deleting own run succeeds
    res_del_a = client.delete(f"/api/runs/{run_a['id']}", headers={"X-API-Key": KEY_A})
    assert res_del_a.status_code == 200
    assert res_del_a.json() == {"deleted": True, "id": run_a["id"]}


def test_db_down_ready_returns_503_and_simulation_returns_saved_false() -> None:
    """Verify /ready returns 503 when DB fails, while /api/simulate survives with saved=false."""
    settings = Settings(
        APP_ENV="development",
        CLOUDPILOT_API_KEY=KEY_A,
        ALLOWED_ORIGIN="http://localhost:5173",
        DEV_AUTH_DISABLED=False,
    )
    app = create_app(settings)
    client = TestClient(app)

    repo: InMemoryRunRepository = app.state.repo
    # Simulate DB unhealthy
    repo.is_healthy = False

    # /health still returns 200 OK
    res_health = client.get("/health")
    assert res_health.status_code == 200

    # /ready returns 503 Service Unavailable
    res_ready = client.get("/ready")
    assert res_ready.status_code == 503
    assert res_ready.json()["status"] == "not ready"

    mock_sim_result = {"time_split": {"methods": {}}, "service_split": {}, "h3": {}}

    # /api/simulate still works and returns simulation result with saved=False
    with (
        mock_simulation(mock_sim_result),
        patch.object(repo, "save_run", side_effect=RuntimeError("DB is offline")),
    ):
        res_sim = client.post(
            "/api/simulate",
            json={"seed": 42, "n_services": 4, "n_steps": 600},
            headers={"X-API-Key": KEY_A},
        )
        assert res_sim.status_code == 200
        sim_data = res_sim.json()
        assert sim_data["saved"] is False
        assert "time_split" in sim_data


@pytest.mark.anyio
async def test_supabase_repository_surfaces_postgrest_error_details() -> None:
    """Verify PostgREST 400 error code and message are surfaced in RuntimeError."""

    def mock_pgrst_error_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "code": "PGRST204",
                "message": (
                    "Could not find the 'client_id' column of 'simulation_runs' in the schema cache"
                ),
                "details": None,
                "hint": None,
            },
        )

    transport = httpx.MockTransport(mock_pgrst_error_handler)
    client = httpx.AsyncClient(
        base_url="https://mock.supabase.co/rest/v1",
        headers={
            "apikey": SECRET_KEY,
            "Authorization": f"Bearer {SECRET_KEY}",
            "Content-Type": "application/json",
        },
        transport=transport,
    )
    repo = SupabaseRunRepository(
        supabase_url="https://mock.supabase.co",
        supabase_service_key=SECRET_KEY,
        client=client,
    )

    with pytest.raises(RuntimeError) as exc_info:
        await repo.save_run("client_a", "simulated", {"seed": 1}, "ok")

    err_msg = str(exc_info.value)
    assert "HTTP 400" in err_msg
    assert "PGRST204" in err_msg
    assert "Could not find the 'client_id' column" in err_msg
    assert SECRET_KEY not in err_msg
