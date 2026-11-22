"""Tests for in-memory sliding window rate limiter."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.conftest import TEST_VALID_KEY


def test_rate_limit_exceeded_returns_429_with_retry_after():
    """Exceeding the rate limit returns 429 with Retry-After header."""
    settings = Settings(
        APP_ENV="development",
        CLOUDPILOT_API_KEY=TEST_VALID_KEY,
        ALLOWED_ORIGIN="http://localhost:5173",
        RATE_LIMIT_PER_MIN=3,
    )
    app = create_app(settings)
    client = TestClient(app)
    headers = {"X-API-Key": TEST_VALID_KEY}

    # First 3 requests should pass
    for _ in range(3):
        res = client.get("/api/ping", headers=headers)
        assert res.status_code == 200

    # 4th request within the window must be rate limited
    blocked_res = client.get("/api/ping", headers=headers)
    assert blocked_res.status_code == 429
    assert blocked_res.json() == {"detail": "Rate limit exceeded"}
    assert "Retry-After" in blocked_res.headers
    retry_after = int(blocked_res.headers["Retry-After"])
    assert retry_after >= 1


def test_rate_limit_tracks_clients_independently():
    """Different client keys have independent rate limit allowances."""
    settings = Settings(
        APP_ENV="development",
        CLOUDPILOT_API_KEY="",
        DEV_AUTH_DISABLED=True,
        ALLOWED_ORIGIN="http://localhost:5173",
        RATE_LIMIT_PER_MIN=2,
    )
    app = create_app(settings)
    client = TestClient(app)

    # Client A consumes allowance
    client.get("/api/ping", headers={"X-API-Key": "key-client-a-1234567890123456"})
    client.get("/api/ping", headers={"X-API-Key": "key-client-a-1234567890123456"})
    blocked_a = client.get("/api/ping", headers={"X-API-Key": "key-client-a-1234567890123456"})
    assert blocked_a.status_code == 429

    # Client B should still have full allowance
    allowed_b = client.get("/api/ping", headers={"X-API-Key": "key-client-b-9876543210987654"})
    assert allowed_b.status_code == 200
