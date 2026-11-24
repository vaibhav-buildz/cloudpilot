"""API key authentication and client identification."""

from __future__ import annotations

import hashlib
import hmac
import uuid

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader

from app.config import Settings, get_settings

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def is_valid_uuid4(val: str) -> bool:
    """Validate that val is a canonical UUID4 string."""
    if not isinstance(val, str) or len(val) != 36:
        return False
    try:
        parsed = uuid.UUID(val, version=4)
        return parsed.version == 4 and str(parsed) == val.lower()
    except (ValueError, AttributeError):
        return False


def hash_client_key(key: str) -> str:
    """Return a short cryptographic hash of the API key for client identification."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def verify_api_key(
    request: Request,
    api_key: str | None = Security(API_KEY_HEADER),
    settings: Settings = Depends(get_settings),
) -> str:
    """Validate X-API-Key header using constant-time comparison and derive scoped client_id.

    In development, if DEV_AUTH_DISABLED is true, requests without a key are allowed.
    If authenticated with an API key AND X-Visitor-Id is present, validates that
    X-Visitor-Id is a UUID4 (returning 422 if invalid). Then computes:
    client_id = sha256(api_key + ":" + visitor_id) (hex).
    The X-Visitor-Id header is never trusted without a valid API key.
    Returns a client identifier string and stores it in request.state.client_id.
    """
    if settings.APP_ENV != "production" and settings.DEV_AUTH_DISABLED:
        if not api_key:
            client_id = "dev-unauthenticated"
            request.state.client_id = client_id
            return client_id
        visitor_id = request.headers.get("X-Visitor-Id")
        if visitor_id is not None:
            if not is_valid_uuid4(visitor_id):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Invalid X-Visitor-Id header; must be a valid UUID4.",
                )
            client_id = hashlib.sha256(f"{api_key}:{visitor_id}".encode()).hexdigest()
        else:
            client_id = hash_client_key(api_key)
        request.state.client_id = client_id
        return client_id

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key in X-API-Key header",
        )

    expected_key = settings.CLOUDPILOT_API_KEY
    if not expected_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Server API key is unconfigured",
        )

    is_valid = hmac.compare_digest(
        api_key.encode("utf-8"),
        expected_key.encode("utf-8"),
    )
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    # API key is authenticated. Validate X-Visitor-Id if present.
    visitor_id = request.headers.get("X-Visitor-Id")
    if visitor_id is not None:
        if not is_valid_uuid4(visitor_id):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid X-Visitor-Id header; must be a valid UUID4.",
            )
        client_id = hashlib.sha256(f"{api_key}:{visitor_id}".encode()).hexdigest()
    else:
        client_id = hash_client_key(api_key)

    request.state.client_id = client_id
    return client_id
