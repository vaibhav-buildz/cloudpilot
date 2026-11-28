"""Health and readiness check endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from app.config import Settings, get_settings

router = APIRouter(tags=["Health"])


@router.get("/health", status_code=status.HTTP_200_OK)
def get_health() -> dict[str, str]:
    """Liveness probe. Always returns 200 OK."""
    return {"status": "ok"}


@router.get("/ready")
async def get_ready(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    """Readiness probe.

    Returns 200 OK when configuration and database dependencies are verified,
    otherwise returns 503 Service Unavailable.
    """
    ready, reason = settings.is_ready()
    if not ready:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not ready", "reason": reason},
        )

    if not request.app.state.simulations.ready:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not ready", "reason": "Simulation worker is warming up"},
        )

    repo = getattr(request.app.state, "repo", None)
    if repo is not None:
        try:
            is_healthy = await repo.ping()
            if not is_healthy:
                return JSONResponse(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    content={"status": "not ready", "reason": "Database ping failed"},
                )
        except Exception:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "not ready", "reason": "Database connection error"},
            )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": "ready"},
    )
