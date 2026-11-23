"""Tests for simulation API endpoints and concurrency enforcement."""

from __future__ import annotations

import io
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.routes.simulate import concurrency_gate
from tests.conftest import TEST_VALID_KEY


def test_methods_endpoint_requires_auth(client: TestClient):
    """Calling /api/methods without authentication must return 401."""
    res = client.get("/api/methods")
    assert res.status_code == 401


def test_methods_endpoint_returns_catalog(client: TestClient):
    """Calling /api/methods with valid key returns method catalog."""
    res = client.get("/api/methods", headers={"X-API-Key": TEST_VALID_KEY})
    assert res.status_code == 200
    methods = res.json()
    assert len(methods) >= 9
    ids = [m["id"] for m in methods]
    assert "static" in ids
    assert "GBR_q95" in ids


def test_simulate_fails_above_configured_caps(client: TestClient):
    """Requesting n_services or n_steps above configured limits returns 422."""
    headers = {"X-API-Key": TEST_VALID_KEY}

    # SIM_MAX_SERVICES is 20 by default
    res = client.post(
        "/api/simulate",
        json={"seed": 42, "n_services": 50, "n_steps": 500},
        headers=headers,
    )
    assert res.status_code == 422
    assert "SIM_MAX_SERVICES" in res.json()["detail"]

    # SIM_MAX_STEPS is 1000 by default
    res2 = client.post(
        "/api/simulate",
        json={"seed": 42, "n_services": 5, "n_steps": 2500},
        headers=headers,
    )
    assert res2.status_code == 422
    assert "SIM_MAX_STEPS" in res2.json()["detail"]


def test_simulate_concurrent_request_returns_429():
    """If a simulation is already running for the client, subsequent requests return 429."""
    settings = Settings(
        APP_ENV="development",
        CLOUDPILOT_API_KEY=TEST_VALID_KEY,
        ALLOWED_ORIGIN="http://localhost:5173",
    )
    app = create_app(settings)
    client = TestClient(app)
    headers = {"X-API-Key": TEST_VALID_KEY}

    # Simulate an active job by manually locking the client ID in the concurrency gate
    from app.security import hash_client_key

    client_key_hash = f"key:{hash_client_key(TEST_VALID_KEY)}"
    concurrency_gate.acquire(client_key_hash)

    try:
        res = client.post(
            "/api/simulate",
            json={"seed": 42, "n_services": 4, "n_steps": 400},
            headers=headers,
        )
        assert res.status_code == 429
        assert "already active" in res.json()["detail"]
    finally:
        concurrency_gate.release(client_key_hash)


def test_simulate_csv_rejects_bad_files(client: TestClient):
    """Uploading CSV with invalid columns or negative CPU returns 422."""
    headers = {"X-API-Key": TEST_VALID_KEY}

    # Missing column
    bad_csv = "service_id,timestamp\nsrv-1,2026-01-01T00:00:00Z\n"
    res = client.post(
        "/api/simulate/csv",
        files={"file": ("workload.csv", io.BytesIO(bad_csv.encode("utf-8")), "text/csv")},
        headers=headers,
    )
    assert res.status_code == 422
    assert "missing required column" in res.json()["detail"].lower()

    # Negative CPU demand
    neg_csv = "service_id,timestamp,cpu_demand\nsrv-1,2026-01-01T00:00:00Z,-5.0\n"
    res2 = client.post(
        "/api/simulate/csv",
        files={"file": ("workload.csv", io.BytesIO(neg_csv.encode("utf-8")), "text/csv")},
        headers=headers,
    )
    assert res2.status_code == 422
    assert "negative" in res2.json()["detail"].lower()


def test_simulate_returns_200_with_expected_keys(client: TestClient):
    """POST /api/simulate returns expected schema on a small fast simulation."""
    headers = {"X-API-Key": TEST_VALID_KEY}

    # Mock run_experiment for fast unit test execution
    mock_response = {
        "disclaimer": "Results describe synthetic workload data.",
        "execution_time_seconds": 1.25,
        "parameters": {"seed": 42, "n_services": 4, "n_steps": 400},
        "time_split": {"comparator": "static", "methods": {}, "h1": {"verdict": "SUPPORTED"}},
        "service_split": {"comparator": "static", "methods": {}, "h2": {"verdict": "SUPPORTED"}},
        "h3": {"verdict": "SUPPORTED", "threshold": 0.015},
    }

    with patch("app.routes.simulate.run_experiment", return_value=mock_response):
        res = client.post(
            "/api/simulate",
            json={"seed": 42, "n_services": 4, "n_steps": 400},
            headers=headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert "disclaimer" in data
        assert "time_split" in data
        assert "service_split" in data
        assert "h3" in data
