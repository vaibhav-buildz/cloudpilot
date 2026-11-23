"""Simulation and method discovery endpoints."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.engine.csv_loader import MAX_CSV_BYTES, load_workload_from_csv
from app.engine.runner import run_experiment
from app.ratelimit import rate_limiter
from app.security import verify_api_key

logger = logging.getLogger("cloudpilot")

router = APIRouter(tags=["Simulation"])


class SimulationConcurrencyGate:
    """Ensure each client runs only one simulation at a time."""

    def __init__(self) -> None:
        self._active_clients: set[str] = set()
        self._lock = threading.Lock()

    def acquire(self, client_id: str) -> bool:
        with self._lock:
            if client_id in self._active_clients:
                return False
            self._active_clients.add(client_id)
            return True

    def release(self, client_id: str) -> None:
        with self._lock:
            self._active_clients.discard(client_id)


concurrency_gate = SimulationConcurrencyGate()


class SimulateRequest(BaseModel):
    """Parameters for synthetic workload simulation."""

    seed: int = Field(default=42, description="Random seed for reproducibility")
    n_services: int = Field(default=8, ge=2, description="Number of services to simulate")
    n_steps: int = Field(default=600, ge=388, description="Number of 5-minute time steps")
    target_violation: float = Field(
        default=0.01,
        ge=0.005,
        le=0.05,
        description="Target pooled violation rate (0.5% to 5.0%)",
    )


class MethodInfo(BaseModel):
    id: str
    name: str
    category: str
    description: str


AVAILABLE_METHODS: list[MethodInfo] = [
    MethodInfo(
        id="static",
        name="Static Reservation",
        category="baseline",
        description="Fixed over-provisioned allocation request per service.",
    ),
    MethodInfo(
        id="rolling_max_48",
        name="Rolling Max (4h)",
        category="baseline",
        description="Maximum past demand observed over the previous 48 intervals (4 hours).",
    ),
    MethodInfo(
        id="rolling_p99",
        name="Rolling p99 (7d)",
        category="baseline",
        description="Expanding 99th percentile over past observations up to 7 days.",
    ),
    MethodInfo(
        id="ewma",
        name="EWMA + Margin",
        category="baseline",
        description="Exponentially weighted moving average with validation-tuned alpha and margin.",
    ),
    MethodInfo(
        id="LR",
        name="Linear Regression + Margin",
        category="model",
        description="Ordinary least squares regressor with validation-tuned safety margin.",
    ),
    MethodInfo(
        id="DT",
        name="Decision Tree + Margin",
        category="model",
        description="Constrained decision tree regressor with validation-tuned safety margin.",
    ),
    MethodInfo(
        id="RF",
        name="Random Forest + Margin",
        category="model",
        description="Ensemble of 100 decision trees with validation-tuned safety margin.",
    ),
    MethodInfo(
        id="GB",
        name="Gradient Boosting + Margin",
        category="model",
        description="Gradient boosted trees optimizing squared error with validation margin.",
    ),
    MethodInfo(
        id="GBR_q95",
        name="Gradient Boosted Quantile 95",
        category="model",
        description="Gradient boosted trees directly predicting 95th percentile with margin.",
    ),
]


@router.get("/methods", response_model=list[MethodInfo])
def get_available_methods() -> list[MethodInfo]:
    """List all supported baseline heuristics and machine learning models."""
    return AVAILABLE_METHODS


@router.post("/simulate")
async def simulate_workload(
    req: SimulateRequest,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    client_id: Annotated[str, Depends(verify_api_key)],
) -> dict[str, Any]:
    """Run simulation on synthetic seeded workload across TIME and SERVICE splits."""
    if req.n_services > settings.SIM_MAX_SERVICES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Requested n_services ({req.n_services}) exceeds configured "
                f"SIM_MAX_SERVICES limit ({settings.SIM_MAX_SERVICES})."
            ),
        )

    if req.n_steps > settings.SIM_MAX_STEPS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Requested n_steps ({req.n_steps}) exceeds configured "
                f"SIM_MAX_STEPS limit ({settings.SIM_MAX_STEPS})."
            ),
        )

    gate_client_id = rate_limiter.extract_client_id(request)
    if not concurrency_gate.acquire(gate_client_id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="A simulation is already active for this client. Please wait for completion.",
        )

    t_start = time.perf_counter()
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                run_experiment,
                seed=req.seed,
                n_services=req.n_services,
                n_steps=req.n_steps,
                target_violation=req.target_violation,
                timeout_seconds=float(settings.SIM_TIMEOUT_SECONDS),
            ),
            timeout=float(settings.SIM_TIMEOUT_SECONDS) + 5.0,
        )
        duration_ms = round((time.perf_counter() - t_start) * 1000)

        # Best-effort persist run
        repo = getattr(request.app.state, "repo", None)
        saved = False
        run_record = None
        if repo is not None:
            try:
                run_record = await repo.save_run(
                    client_id=client_id,
                    source="simulated",
                    params={
                        "seed": req.seed,
                        "n_services": req.n_services,
                        "n_steps": req.n_steps,
                        "target_violation": req.target_violation,
                    },
                    status="ok",
                    result=result,
                    duration_ms=duration_ms,
                )
                await repo.prune(client_id=client_id, keep=50)
                saved = True
            except Exception as exc:
                logger.warning(
                    "Failed to persist simulation run",
                    extra={"error": type(exc).__name__, "client_id": client_id},
                )
                saved = False

        result["saved"] = saved
        if run_record and "id" in run_record:
            result["run_id"] = run_record["id"]
        return result
    except TimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Simulation timed out after {settings.SIM_TIMEOUT_SECONDS} seconds.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Simulation failed: {exc}",
        ) from exc
    finally:
        concurrency_gate.release(gate_client_id)


@router.post("/simulate/csv")
async def simulate_csv_workload(
    file: Annotated[UploadFile, File(...)],
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    client_id: Annotated[str, Depends(verify_api_key)],
    target_violation: float = Query(default=0.01, ge=0.005, le=0.05),
) -> dict[str, Any]:
    """Execute allocation experiment on user-uploaded workload CSV."""
    contents = await file.read()
    if len(contents) > MAX_CSV_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Uploaded CSV exceeds the maximum allowed 5 MB payload limit.",
        )

    try:
        workload = load_workload_from_csv(contents)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    n_services = workload.demand.shape[0]
    n_steps = workload.demand.shape[1]

    if n_services > settings.SIM_MAX_SERVICES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"CSV contains {n_services} services, exceeding configured "
                f"SIM_MAX_SERVICES limit ({settings.SIM_MAX_SERVICES})."
            ),
        )

    if n_steps > settings.SIM_MAX_STEPS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"CSV contains {n_steps} time steps, exceeding configured "
                f"SIM_MAX_STEPS limit ({settings.SIM_MAX_STEPS})."
            ),
        )

    gate_client_id = rate_limiter.extract_client_id(request)
    if not concurrency_gate.acquire(gate_client_id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="A simulation is already active for this client. Please wait for completion.",
        )

    t_start = time.perf_counter()
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                run_experiment,
                seed=42,
                n_services=n_services,
                n_steps=n_steps,
                target_violation=target_violation,
                timeout_seconds=float(settings.SIM_TIMEOUT_SECONDS),
                workload=workload,
            ),
            timeout=float(settings.SIM_TIMEOUT_SECONDS) + 5.0,
        )
        duration_ms = round((time.perf_counter() - t_start) * 1000)

        # Best-effort persist run without saving CSV content or file names
        repo = getattr(request.app.state, "repo", None)
        saved = False
        run_record = None
        if repo is not None:
            try:
                run_record = await repo.save_run(
                    client_id=client_id,
                    source="csv",
                    params={
                        "n_services": n_services,
                        "n_steps": n_steps,
                        "target_violation": target_violation,
                    },
                    status="ok",
                    result=result,
                    duration_ms=duration_ms,
                )
                await repo.prune(client_id=client_id, keep=50)
                saved = True
            except Exception as exc:
                logger.warning(
                    "Failed to persist CSV simulation run",
                    extra={"error": type(exc).__name__, "client_id": client_id},
                )
                saved = False

        result["saved"] = saved
        if run_record and "id" in run_record:
            result["run_id"] = run_record["id"]
        return result
    except TimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Simulation timed out after {settings.SIM_TIMEOUT_SECONDS} seconds.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Simulation failed: {exc}",
        ) from exc
    finally:
        concurrency_gate.release(gate_client_id)
