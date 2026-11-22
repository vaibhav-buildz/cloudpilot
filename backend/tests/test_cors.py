"""Tests for strict CORS enforcement."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.conftest import TEST_VALID_KEY


def test_cors_allows_configured_origin():
    """Requests with allowed origin get the access-control-allow-origin header."""
    settings = Settings(
        APP_ENV="development",
        CLOUDPILOT_API_KEY=TEST_VALID_KEY,
        ALLOWED_ORIGIN="http://localhost:5173,https://dashboard.example.com",
    )
    app = create_app(settings)
    client = TestClient(app)

    # Simple GET request with allowed Origin
    response = client.get(
        "/health",
        headers={"Origin": "http://localhost:5173"},
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_rejects_unconfigured_origin():
    """Requests with unauthorized origin do not get access-control-allow-origin."""
    settings = Settings(
        APP_ENV="development",
        CLOUDPILOT_API_KEY=TEST_VALID_KEY,
        ALLOWED_ORIGIN="http://localhost:5173",
    )
    app = create_app(settings)
    client = TestClient(app)

    response = client.get(
        "/health",
        headers={"Origin": "http://evil-site.com"},
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") is None


def test_cors_preflight_options():
    """OPTIONS preflight from allowed origin returns proper CORS headers."""
    settings = Settings(
        APP_ENV="development",
        CLOUDPILOT_API_KEY=TEST_VALID_KEY,
        ALLOWED_ORIGIN="http://localhost:5173",
    )
    app = create_app(settings)
    client = TestClient(app)

    response = client.options(
        "/api/ping",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-API-Key",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
