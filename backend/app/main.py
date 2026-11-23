"""FastAPI application factory and middleware configuration."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import Settings, get_settings
from app.db.repository import get_repository
from app.logging_setup import setup_logging
from app.ratelimit import rate_limiter
from app.routes.health import router as health_router
from app.routes.runs import router as runs_router
from app.routes.simulate import router as simulate_router
from app.security import verify_api_key

logger = logging.getLogger("cloudpilot")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure a CloudPilot FastAPI application instance."""
    app_settings = settings or get_settings()

    # Fail closed immediately if configuration is invalid
    app_settings.validate_fail_closed()

    # Initialize structured JSON logging
    setup_logging()

    # Initialize persistence repository
    repo = get_repository(app_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info(
            "CloudPilot control plane started",
            extra={"app_env": app_settings.APP_ENV},
        )
        yield
        if hasattr(repo, "aclose"):
            await repo.aclose()
        logger.info("CloudPilot control plane stopping")

    app = FastAPI(
        title="CloudPilot Backend",
        description="ML-based CPU resource allocation engine for cloud workloads",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Store settings, repository, and wire dependency override for consistent app instances
    app.state.settings = app_settings
    app.state.repo = repo
    app.dependency_overrides[get_settings] = lambda: app_settings

    # Strict CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-API-Key", "Authorization", "X-Request-ID"],
    )

    @app.middleware("http")
    async def security_and_telemetry_middleware(request: Request, call_next) -> Response:
        """Enforce payload size limits, request IDs, security headers, and structured logging."""
        start_time = time.perf_counter()

        # Request ID handling
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex

        # Enforce maximum request body size (1 MB default limit, bypassed for 5 MB CSV multipart)
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                # If uploading to /api/simulate/csv, allow up to 5 MB
                max_bytes = (
                    5 * 1024 * 1024
                    if request.url.path == "/api/simulate/csv"
                    else app_settings.MAX_REQUEST_BODY_BYTES
                )
                if int(content_length) > max_bytes:
                    return JSONResponse(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        content={"detail": "Request body exceeds allowed size limit"},
                        headers={"X-Request-ID": request_id},
                    )
            except ValueError:
                pass

        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "Unhandled error during request processing",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                },
            )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Internal server error"},
                headers={"X-Request-ID": request_id},
            )

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Apply standard security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Request-ID"] = request_id

        # Log request completion with structured telemetry (secrets are strictly excluded)
        client_ip = request.client.host if request.client else "unknown"
        logger.info(
            f"{request.method} {request.url.path} -> {response.status_code}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "client_ip": client_ip,
                "duration_ms": duration_ms,
            },
        )

        return response

    # Public routes
    app.include_router(health_router)

    # Protected /api router with API key authentication and sliding window rate limiting
    api_router = APIRouter(
        prefix="/api",
        tags=["API"],
        dependencies=[
            Depends(verify_api_key),
            Depends(rate_limiter.check),
        ],
    )

    @api_router.get("/ping")
    def ping() -> dict[str, bool]:
        """Protected placeholder endpoint to verify authentication and rate limiting."""
        return {"pong": True}

    api_router.include_router(simulate_router)
    api_router.include_router(runs_router)

    app.include_router(api_router)

    return app
