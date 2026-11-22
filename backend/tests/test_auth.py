"""Tests for API key authentication."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.conftest import TEST_VALID_KEY


def test_api_ping_fails_without_key(client: TestClient):
    """Calling /api/ping without X-API-Key header must return 401."""
    response = client.get("/api/ping")
    assert response.status_code == 401
    assert "Missing API key" in response.json()["detail"]


def test_api_ping_fails_with_invalid_key(client: TestClient):
    """Calling /api/ping with an invalid X-API-Key header must return 401."""
    response = client.get("/api/ping", headers={"X-API-Key": "wrong-key-content-12345"})
    assert response.status_code == 401
    assert "Invalid API key" in response.json()["detail"]


def test_api_ping_succeeds_with_valid_key(client: TestClient):
    """Calling /api/ping with valid key must return 200 {"pong": True}."""
    response = client.get("/api/ping", headers={"X-API-Key": TEST_VALID_KEY})
    assert response.status_code == 200
    assert response.json() == {"pong": True}


def test_api_ping_succeeds_in_dev_with_auth_disabled():
    """In development with DEV_AUTH_DISABLED=True, requests pass without key."""
    settings = Settings(
        APP_ENV="development",
        CLOUDPILOT_API_KEY="",
        DEV_AUTH_DISABLED=True,
        ALLOWED_ORIGIN="http://localhost:5173",
    )
    app = create_app(settings)
    client = TestClient(app)

    response = client.get("/api/ping")
    assert response.status_code == 200
    assert response.json() == {"pong": True}
