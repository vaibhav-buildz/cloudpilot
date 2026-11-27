"""Tests for visitor scoping, global simulation limiter, and /api/limits."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.config import Settings
from app.engine.csv_loader import MAX_CSV_BYTES
from app.main import create_app
from app.ratelimit import global_sim_limiter, rate_limiter
from tests.conftest import TEST_VALID_KEY, mock_simulation

VISITOR_1 = "11111111-1111-4111-8111-111111111111"
VISITOR_2 = "22222222-2222-4222-8222-222222222222"
INVALID_VISITOR_UUID = "not-a-valid-uuid"
# UUID v1 (version nibble is 1 instead of 4)
UUID_V1 = "6ba7b810-9dad-11d1-80b4-00c04fd430c8"


def test_two_visitors_have_separate_history() -> None:
    """Two visitors using the same API key must have completely isolated run histories."""
    settings = Settings(
        APP_ENV="development",
        CLOUDPILOT_API_KEY=TEST_VALID_KEY,
        ALLOWED_ORIGIN="http://localhost:5173",
        DEV_AUTH_DISABLED=False,
    )
    app = create_app(settings)
    client = TestClient(app)

    # Save run for Visitor 1
    mock_result_1 = {"id": "v1_result", "time_split": {}, "service_split": {}, "h3": {}}
    with mock_simulation(mock_result_1):
        res_v1 = client.post(
            "/api/simulate",
            json={"seed": 1, "n_services": 4, "n_steps": 600},
            headers={"X-API-Key": TEST_VALID_KEY, "X-Visitor-Id": VISITOR_1},
        )
        assert res_v1.status_code == 200
        assert res_v1.json()["saved"] is True
        run1_id = res_v1.json()["run_id"]

    # Save run for Visitor 2
    mock_result_2 = {"id": "v2_result", "time_split": {}, "service_split": {}, "h3": {}}
    with mock_simulation(mock_result_2):
        res_v2 = client.post(
            "/api/simulate",
            json={"seed": 2, "n_services": 4, "n_steps": 600},
            headers={"X-API-Key": TEST_VALID_KEY, "X-Visitor-Id": VISITOR_2},
        )
        assert res_v2.status_code == 200
        assert res_v2.json()["saved"] is True
        run2_id = res_v2.json()["run_id"]

    assert run1_id != run2_id

    # Visitor 1 lists runs: should only see run1
    list_v1 = client.get(
        "/api/runs",
        headers={"X-API-Key": TEST_VALID_KEY, "X-Visitor-Id": VISITOR_1},
    )
    assert list_v1.status_code == 200
    runs_1 = list_v1.json()
    assert len(runs_1) == 1
    assert runs_1[0]["id"] == run1_id

    # Visitor 2 lists runs: should only see run2
    list_v2 = client.get(
        "/api/runs",
        headers={"X-API-Key": TEST_VALID_KEY, "X-Visitor-Id": VISITOR_2},
    )
    assert list_v2.status_code == 200
    runs_2 = list_v2.json()
    assert len(runs_2) == 1
    assert runs_2[0]["id"] == run2_id

    # Visitor 1 cannot get Visitor 2's run
    get_v2_from_v1 = client.get(
        f"/api/runs/{run2_id}",
        headers={"X-API-Key": TEST_VALID_KEY, "X-Visitor-Id": VISITOR_1},
    )
    assert get_v2_from_v1.status_code == 404

    # Visitor 1 cannot delete Visitor 2's run
    del_v2_from_v1 = client.delete(
        f"/api/runs/{run2_id}",
        headers={"X-API-Key": TEST_VALID_KEY, "X-Visitor-Id": VISITOR_1},
    )
    assert del_v2_from_v1.status_code == 404


def test_two_visitors_have_separate_rate_limits() -> None:
    """One visitor exhausting rate limits must not affect another visitor with the same key."""
    rate_limiter.reset()
    settings = Settings(
        APP_ENV="development",
        CLOUDPILOT_API_KEY=TEST_VALID_KEY,
        RATE_LIMIT_PER_MIN=3,
        ALLOWED_ORIGIN="http://localhost:5173",
        DEV_AUTH_DISABLED=False,
    )
    app = create_app(settings)
    client = TestClient(app)

    headers_v1 = {"X-API-Key": TEST_VALID_KEY, "X-Visitor-Id": VISITOR_1}
    headers_v2 = {"X-API-Key": TEST_VALID_KEY, "X-Visitor-Id": VISITOR_2}

    # Visitor 1 uses all 3 requests
    for _ in range(3):
        res = client.get("/api/ping", headers=headers_v1)
        assert res.status_code == 200

    # Visitor 1 request 4 is rate-limited (429)
    res_v1_blocked = client.get("/api/ping", headers=headers_v1)
    assert res_v1_blocked.status_code == 429
    assert "Retry-After" in res_v1_blocked.headers

    # Visitor 2 with the same key is NOT rate-limited
    res_v2_ok = client.get("/api/ping", headers=headers_v2)
    assert res_v2_ok.status_code == 200


def test_invalid_visitor_id_returns_422() -> None:
    """If X-Visitor-Id is provided but is not a valid canonical UUID4, return 422."""
    settings = Settings(
        APP_ENV="development",
        CLOUDPILOT_API_KEY=TEST_VALID_KEY,
        ALLOWED_ORIGIN="http://localhost:5173",
    )
    app = create_app(settings)
    client = TestClient(app)

    # Completely malformed string
    res_bad = client.get(
        "/api/ping",
        headers={"X-API-Key": TEST_VALID_KEY, "X-Visitor-Id": INVALID_VISITOR_UUID},
    )
    assert res_bad.status_code == 422
    assert "UUID4" in res_bad.json()["detail"]

    # Valid UUID but version 1 instead of version 4
    res_v1_uuid = client.get(
        "/api/ping",
        headers={"X-API-Key": TEST_VALID_KEY, "X-Visitor-Id": UUID_V1},
    )
    assert res_v1_uuid.status_code == 422
    assert "UUID4" in res_v1_uuid.json()["detail"]


def test_visitor_id_never_trusted_without_valid_api_key() -> None:
    """X-Visitor-Id must never grant access or be validated if API key is missing or invalid."""
    settings = Settings(
        APP_ENV="development",
        CLOUDPILOT_API_KEY=TEST_VALID_KEY,
        ALLOWED_ORIGIN="http://localhost:5173",
        DEV_AUTH_DISABLED=False,
    )
    app = create_app(settings)
    client = TestClient(app)

    # Missing API key entirely
    res_no_key = client.get(
        "/api/ping",
        headers={"X-Visitor-Id": VISITOR_1},
    )
    assert res_no_key.status_code == 401

    # Invalid API key with valid visitor ID
    res_bad_key = client.get(
        "/api/ping",
        headers={"X-API-Key": "wrong-key-" + "x" * 25, "X-Visitor-Id": VISITOR_1},
    )
    assert res_bad_key.status_code == 401

    # Invalid API key with invalid visitor ID returns 401 first (key check happens first)
    res_bad_both = client.get(
        "/api/ping",
        headers={"X-API-Key": "wrong-key-" + "x" * 25, "X-Visitor-Id": "invalid-uuid"},
    )
    assert res_bad_both.status_code == 401


def test_global_simulation_limiter_returns_429() -> None:
    """Global limiter caps total simulations across all clients with 429 Retry-After."""
    global_sim_limiter.reset()
    settings = Settings(
        APP_ENV="development",
        CLOUDPILOT_API_KEY=TEST_VALID_KEY,
        GLOBAL_SIM_PER_MIN=2,
        ALLOWED_ORIGIN="http://localhost:5173",
    )
    app = create_app(settings)
    client = TestClient(app)

    mock_res = {"time_split": {}, "service_split": {}, "h3": {}}

    with mock_simulation(mock_res):
        # Request 1 from Visitor 1
        res1 = client.post(
            "/api/simulate",
            json={"seed": 1, "n_services": 4, "n_steps": 600},
            headers={"X-API-Key": TEST_VALID_KEY, "X-Visitor-Id": VISITOR_1},
        )
        assert res1.status_code == 200

        # Request 2 from Visitor 2
        res2 = client.post(
            "/api/simulate",
            json={"seed": 2, "n_services": 4, "n_steps": 600},
            headers={"X-API-Key": TEST_VALID_KEY, "X-Visitor-Id": VISITOR_2},
        )
        assert res2.status_code == 200

        # Request 3 (from any visitor) exceeds global limit of 2 -> 429
        res3 = client.post(
            "/api/simulate",
            json={"seed": 3, "n_services": 4, "n_steps": 600},
            headers={"X-API-Key": TEST_VALID_KEY, "X-Visitor-Id": str(uuid.uuid4())},
        )
        assert res3.status_code == 429
        assert "Retry-After" in res3.headers
        assert "Global simulation rate limit exceeded" in res3.json()["detail"]


def test_get_limits_endpoint() -> None:
    """GET /api/limits must return configured simulation limits matching settings."""
    settings = Settings(
        APP_ENV="development",
        CLOUDPILOT_API_KEY=TEST_VALID_KEY,
        SIM_MAX_SERVICES=16,
        SIM_MAX_STEPS=800,
        SIM_TIMEOUT_SECONDS=45,
        ALLOWED_ORIGIN="http://localhost:5173",
    )
    app = create_app(settings)
    client = TestClient(app)

    # 1. Calling without auth returns 401
    unauth = client.get("/api/limits")
    assert unauth.status_code == 401

    # 2. Calling with auth returns exact configuration
    res = client.get("/api/limits", headers={"X-API-Key": TEST_VALID_KEY})
    assert res.status_code == 200
    data = res.json()

    assert data["max_services"] == 16
    assert data["max_steps"] == 800
    assert data["max_csv_bytes"] == MAX_CSV_BYTES
    assert data["timeout_seconds"] == 45
    assert data["history_limit"] == 50
