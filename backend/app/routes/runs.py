"""Simulation run management endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.db.repository import RunRepository
from app.security import verify_api_key

router = APIRouter(prefix="/runs", tags=["Runs"])


def get_repo(request: Request) -> RunRepository:
    """Retrieve repository instance from application state."""
    return request.app.state.repo


def validate_uuid(run_id: str) -> str:
    """Validate that run_id is a valid UUID string, returning 422 on failure."""
    try:
        val = uuid.UUID(run_id)
        return str(val)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid run ID format; must be a valid UUID.",
        ) from exc


@router.get("", response_model=list[dict[str, Any]])
async def list_runs(
    client_id: Annotated[str, Depends(verify_api_key)],
    repo: Annotated[RunRepository, Depends(get_repo)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[dict[str, Any]]:
    """List simulation runs for authenticated client ordered by created_at desc."""
    return await repo.list_runs(client_id=client_id, limit=limit, offset=offset)


@router.get("/{id}")
async def get_run(
    id: str,
    client_id: Annotated[str, Depends(verify_api_key)],
    repo: Annotated[RunRepository, Depends(get_repo)],
) -> dict[str, Any]:
    """Retrieve a single run by ID scoped to the authenticated client."""
    valid_id = validate_uuid(id)
    run = await repo.get_run(client_id=client_id, run_id=valid_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found.",
        )
    return run


@router.delete("/{id}")
async def delete_run(
    id: str,
    client_id: Annotated[str, Depends(verify_api_key)],
    repo: Annotated[RunRepository, Depends(get_repo)],
) -> dict[str, Any]:
    """Delete a single run by ID scoped to the authenticated client."""
    valid_id = validate_uuid(id)
    deleted = await repo.delete_run(client_id=client_id, run_id=valid_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found.",
        )
    return {"deleted": True, "id": valid_id}
