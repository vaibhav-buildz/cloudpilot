"""Tests for fail-closed configuration validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.main import create_app

VALID_KEY = "a" * 32
SHORT_KEY = "a" * 31


def test_production_fails_with_missing_key():
    """Production mode must refuse to initialize if CLOUDPILOT_API_KEY is missing."""
    with pytest.raises(ValidationError, match="CLOUDPILOT_API_KEY"):
        Settings(
            APP_ENV="production",
            CLOUDPILOT_API_KEY="",
            ALLOWED_ORIGIN="https://cloudpilot.example.com",
        )


def test_production_fails_with_short_key():
    """Production mode must refuse keys shorter than 32 characters."""
    with pytest.raises(ValidationError, match="at least 32 characters"):
        Settings(
            APP_ENV="production",
            CLOUDPILOT_API_KEY=SHORT_KEY,
            ALLOWED_ORIGIN="https://cloudpilot.example.com",
        )


def test_production_fails_with_wildcard_origin():
    """Production mode must refuse wildcard ALLOWED_ORIGIN."""
    with pytest.raises(ValidationError, match="wildcard"):
        Settings(
            APP_ENV="production",
            CLOUDPILOT_API_KEY=VALID_KEY,
            ALLOWED_ORIGIN="*",
        )


def test_production_fails_with_wildcard_in_origin_list():
    """Production mode must refuse wildcard inside comma-separated origins."""
    with pytest.raises(ValidationError, match="wildcard"):
        Settings(
            APP_ENV="production",
            CLOUDPILOT_API_KEY=VALID_KEY,
            ALLOWED_ORIGIN="https://app.example.com,*",
        )


def test_production_starts_with_valid_settings():
    """Production mode must start properly when all parameters meet security requirements."""
    settings = Settings(
        APP_ENV="production",
        CLOUDPILOT_API_KEY=VALID_KEY,
        ALLOWED_ORIGIN="https://cloudpilot.example.com",
        SUPABASE_URL="https://project.supabase.co",
        SUPABASE_SERVICE_KEY="test-service-key-12345",
    )
    app = create_app(settings)
    assert app is not None
    assert settings.is_ready()[0] is True


def test_production_fails_without_supabase_url():
    """Production mode must refuse to start if SUPABASE_URL is missing."""
    with pytest.raises(ValidationError, match="SUPABASE_URL"):
        Settings(
            APP_ENV="production",
            CLOUDPILOT_API_KEY=VALID_KEY,
            ALLOWED_ORIGIN="https://cloudpilot.example.com",
            SUPABASE_URL="",
            SUPABASE_SERVICE_KEY="test-service-key-12345",
        )


def test_production_fails_with_insecure_http_supabase_url():
    """Production mode must refuse http:// SUPABASE_URL."""
    with pytest.raises(ValidationError, match="https://"):
        Settings(
            APP_ENV="production",
            CLOUDPILOT_API_KEY=VALID_KEY,
            ALLOWED_ORIGIN="https://cloudpilot.example.com",
            SUPABASE_URL="http://project.supabase.co",
            SUPABASE_SERVICE_KEY="test-service-key-12345",
        )


def test_production_fails_without_supabase_service_key():
    """Production mode must refuse to start if SUPABASE_SERVICE_KEY is missing."""
    with pytest.raises(ValidationError, match="SUPABASE_SERVICE_KEY"):
        Settings(
            APP_ENV="production",
            CLOUDPILOT_API_KEY=VALID_KEY,
            ALLOWED_ORIGIN="https://cloudpilot.example.com",
            SUPABASE_URL="https://project.supabase.co",
            SUPABASE_SERVICE_KEY="",
        )


def test_dev_fails_without_key_when_dev_auth_disabled_is_false():
    """In development, missing key must fail closed unless DEV_AUTH_DISABLED=true."""
    with pytest.raises(ValidationError, match="DEV_AUTH_DISABLED=true"):
        Settings(
            APP_ENV="development",
            CLOUDPILOT_API_KEY="",
            DEV_AUTH_DISABLED=False,
            ALLOWED_ORIGIN="http://localhost:5173",
        )


def test_dev_succeeds_without_key_when_dev_auth_disabled_is_true():
    """In development, missing key is accepted only if DEV_AUTH_DISABLED is explicitly true."""
    settings = Settings(
        APP_ENV="development",
        CLOUDPILOT_API_KEY="",
        DEV_AUTH_DISABLED=True,
        ALLOWED_ORIGIN="http://localhost:5173",
    )
    app = create_app(settings)
    assert app is not None
