"""Tests verifying structured JSON logging and strict secret redaction."""

from __future__ import annotations

import io
import json
import logging

from fastapi.testclient import TestClient

from app.config import Settings
from app.logging_setup import JsonFormatter, SecretFilter, mask_secrets
from app.main import create_app
from tests.conftest import TEST_VALID_KEY


def test_mask_secrets_redacts_keys():
    """mask_secrets replaces sensitive values with [REDACTED]."""
    sample = f"Header was X-API-Key: {TEST_VALID_KEY} and token: supersecretvalue123"
    sanitized = mask_secrets(sample)
    assert TEST_VALID_KEY not in sanitized
    assert "supersecretvalue123" not in sanitized
    assert "[REDACTED]" in sanitized


def test_logs_do_not_contain_api_key():
    """Logs emitted during authenticated requests do not contain the raw API key."""
    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(SecretFilter())

    app_logger = logging.getLogger("cloudpilot")
    app_logger.addHandler(handler)
    app_logger.setLevel(logging.INFO)

    try:
        settings = Settings(
            APP_ENV="development",
            CLOUDPILOT_API_KEY=TEST_VALID_KEY,
            ALLOWED_ORIGIN="http://localhost:5173",
        )
        app = create_app(settings)
        client = TestClient(app)

        response = client.get("/api/ping", headers={"X-API-Key": TEST_VALID_KEY})
        assert response.status_code == 200

        # Log an explicit message simulating an engineer logging headers
        app_logger.info(f"Incoming request authorization: api_key={TEST_VALID_KEY}")

        captured = log_capture.getvalue()
        assert TEST_VALID_KEY not in captured
        assert "[REDACTED]" in captured

        # Verify structured JSON lines
        for line in captured.strip().splitlines():
            data = json.loads(line)
            assert "timestamp" in data
            assert "level" in data
            assert "message" in data
            assert TEST_VALID_KEY not in json.dumps(data)
    finally:
        app_logger.removeHandler(handler)
