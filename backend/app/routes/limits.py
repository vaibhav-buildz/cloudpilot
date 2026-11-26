"""System and simulation limits discovery endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.engine.csv_loader import MAX_CSV_BYTES
from app.engine.extended import WEB_MAX_SERVICES, WEB_MAX_STEPS
from app.security import verify_api_key

router = APIRouter(tags=["Limits"])


class LimitsResponse(BaseModel):
    max_services: int
    max_steps: int
    max_csv_bytes: int
    timeout_seconds: int
    history_limit: int
    extended_max_services: int | None = None
    extended_max_steps: int | None = None


@router.get("/limits", response_model=LimitsResponse)
def get_limits(
    settings: Annotated[Settings, Depends(get_settings)],
    client_id: Annotated[str, Depends(verify_api_key)],
) -> LimitsResponse:
    """Return active simulation caps and system limits."""
    return LimitsResponse(
        max_services=settings.SIM_MAX_SERVICES,
        max_steps=settings.SIM_MAX_STEPS,
        max_csv_bytes=MAX_CSV_BYTES,
        timeout_seconds=settings.SIM_TIMEOUT_SECONDS,
        history_limit=50,
        extended_max_services=(
            min(settings.SIM_MAX_SERVICES, WEB_MAX_SERVICES)
            if settings.extended_simulation_enabled
            else None
        ),
        extended_max_steps=(
            min(settings.SIM_MAX_STEPS, WEB_MAX_STEPS)
            if settings.extended_simulation_enabled
            else None
        ),
    )
