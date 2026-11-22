"""Tests for security headers, request ID handling, and request payload limits."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.conftest import TEST_VALID_KEY


def test_security_headers_present_on_response(client: TestClient):
    """Every response must include secure defaults."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "X-Request-ID" in response.headers


def test_request_id_propagates(client: TestClient):
    """If client supplies X-Request-ID, the response echoes it."""
    custom_id = "custom-req-id-12345"
    response = client.get("/health", headers={"X-Request-ID": custom_id})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == custom_id


def test_payload_size_limit_rejects_large_bodies():
    """Requests exceeding 1 MB limit return 413 Request Entity Too Large."""
    settings = Settings(
        APP_ENV="development",
        CLOUDPILOT_API_KEY=TEST_VALID_KEY,
        ALLOWED_ORIGIN="http://localhost:5173",
        MAX_REQUEST_BODY_BYTES=1024,  # Use 1 KB for test simplicity
    )
    app = create_app(settings)
    client = TestClient(app)

    # 2 KB body exceeding the 1 KB limit
    large_payload = "a" * 2048
    response = client.post(
        "/health",  # route doesn't matter; middleware intercepts before route
        content=large_payload,
        headers={"Content-Length": str(len(large_payload))},
    )
    assert response.status_code == 413
    assert "exceeds" in response.json()["detail"]
