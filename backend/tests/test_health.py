"""Tests for health and readiness endpoints."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.conftest import TEST_VALID_KEY


def test_health_returns_200(client: TestClient):
    """Liveness probe /health must always return 200 and status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_returns_200_when_healthy(client: TestClient):
    """Readiness probe /ready returns 200 when settings are valid."""
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_ready_returns_503_when_unready():
    """Readiness probe /ready returns 503 if verification fails."""
    settings = Settings(
        APP_ENV="development",
        CLOUDPILOT_API_KEY=TEST_VALID_KEY,
        ALLOWED_ORIGIN="http://localhost:5173",
    )
    app = create_app(settings)
    client = TestClient(app)

    with patch.object(Settings, "is_ready", return_value=(False, "Database connection failed")):
        response = client.get("/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not ready"
        assert "Database connection failed" in data["reason"]
