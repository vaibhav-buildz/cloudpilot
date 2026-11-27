"""Pytest fixtures and configuration."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import create_app
from app.ratelimit import global_sim_limiter, rate_limiter

TEST_VALID_KEY = "test_key_with_a_length_of_at_least_32_characters_for_cloudpilot"


@pytest.fixture(autouse=True)
def isolate_settings_from_dotenv(monkeypatch: pytest.MonkeyPatch):
    """Prevent unit tests from reading local .env files or hitting live Supabase."""
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset the in-memory sliding window rate limiter before each test."""
    rate_limiter.reset()
    global_sim_limiter.reset()
    yield
    rate_limiter.reset()
    global_sim_limiter.reset()


def mock_simulation(result: dict):
    async def run(settings, mode, max_services, max_steps, parameters, contents):
        return json.dumps({"parameters": parameters, **result}).encode()

    return patch("app.simulation_process.SimulationProcesses.run", side_effect=run)


@pytest.fixture
def valid_dev_settings() -> Settings:
    """Return valid development settings with a strong API key."""
    return Settings(
        APP_ENV="development",
        CLOUDPILOT_API_KEY=TEST_VALID_KEY,
        DEV_AUTH_DISABLED=False,
        ALLOWED_ORIGIN="http://localhost:5173",
        RATE_LIMIT_PER_MIN=30,
    )


@pytest.fixture
def dev_auth_disabled_settings() -> Settings:
    """Return development settings with auth disabled and no key."""
    return Settings(
        APP_ENV="development",
        CLOUDPILOT_API_KEY="",
        DEV_AUTH_DISABLED=True,
        ALLOWED_ORIGIN="http://localhost:5173",
        RATE_LIMIT_PER_MIN=30,
    )


@pytest.fixture
def valid_prod_settings() -> Settings:
    """Return valid production settings."""
    return Settings(
        APP_ENV="production",
        CLOUDPILOT_API_KEY=TEST_VALID_KEY,
        ALLOWED_ORIGIN="https://cloudpilot.example.com",
        RATE_LIMIT_PER_MIN=30,
    )


@pytest.fixture
def client(valid_dev_settings: Settings) -> TestClient:
    """Create a TestClient with valid development settings."""
    app = create_app(valid_dev_settings)
    app.dependency_overrides[get_settings] = lambda: valid_dev_settings
    return TestClient(app)
