"""Structured JSON logging configuration with secret masking."""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import UTC, datetime
from typing import Any

# Patterns matching potential credentials, tokens, or auth headers
KEY_VALUE_PATTERN = re.compile(
    r"(?i)(api[_-]?key|token|secret|password|authorization)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-]{8,})['\"]?"
)
SUPABASE_PATTERN = re.compile(r"sb_secret_[a-zA-Z0-9_\-]+")
RENDER_PATTERN = re.compile(r"rnd_[a-zA-Z0-9]+")


def mask_secrets(text: str) -> str:
    """Mask sensitive keys, tokens, and authorization values within strings."""
    if not isinstance(text, str):
        return text

    masked = KEY_VALUE_PATTERN.sub(r"\1: [REDACTED]", text)
    masked = SUPABASE_PATTERN.sub("[REDACTED]", masked)
    masked = RENDER_PATTERN.sub("[REDACTED]", masked)
    return masked


class JsonFormatter(logging.Formatter):
    """Format log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        raw_message = record.getMessage()
        sanitized_message = mask_secrets(raw_message)

        log_data: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": sanitized_message,
        }

        # Include standard HTTP request metadata if attached to record
        for attr in ("request_id", "method", "path", "status_code", "client_ip", "duration_ms"):
            if hasattr(record, attr):
                val = getattr(record, attr)
                if isinstance(val, str):
                    val = mask_secrets(val)
                log_data[attr] = val

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, default=str)


class SecretFilter(logging.Filter):
    """Filter to ensure secrets are scrubbed before reaching any handler."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = mask_secrets(record.msg)
        return True


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Initialize structured JSON logging for the application."""
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level.upper())

    # Avoid duplicate handlers if setup is called multiple times
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(SecretFilter())
    root_logger.addHandler(handler)

    return logging.getLogger("cloudpilot")
