"""Simulation and method discovery endpoints."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Annotated, Literal

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.ratelimit import global_sim_limiter, rate_limiter
from app.security import verify_api_key
from app.workload_limits import MAX_CSV_BYTES, MIN_WORKLOAD_SERVICES, MIN_WORKLOAD_STEPS

logger = logging.getLogger("cloudpilot")
router = APIRouter(tags=["Simulation"])
ExperimentMode = Literal["cpu-only", "extended-v1"]
MODE = "extended-v1"


def require_extended_enabled(mode: ExperimentMode, settings: Settings, request: Request) -> None:
    canary = (
        settings.APP_ENV == "production"
        and settings.ENABLE_PRODUCTION_EXTENDED_CANARY
        and request.headers.get("X-CloudPilot-Extended-Canary") == "1"
    )
    if mode == MODE and not (settings.extended_simulation_enabled or canary):
        raise HTTPException(403, "Extended simulation is available offline only.")


class SimulateRequest(BaseModel):
    """Parameters for synthetic workload simulation."""

    seed: int = Field(default=42, ge=0, description="Random seed for reproducibility")
    mode: ExperimentMode = "cpu-only"
    n_services: int = Field(
        default=8, ge=MIN_WORKLOAD_SERVICES, description="Number of services to simulate"
    )
    n_steps: int = Field(
        default=600, ge=MIN_WORKLOAD_STEPS, description="Number of 5-minute time steps"
    )
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


async def wait_for_disconnect(request: Request) -> None:
    # FastAPI has consumed the JSON or multipart body before admitting work.
    while (await request.receive())["type"] != "http.disconnect":
        pass


async def persist_result(
    request: Request, client_id: str, source: str, mode: str, result: dict, duration_ms: int
) -> dict:
    repo = getattr(request.app.state, "repo", None)
    if repo is None:
        return {"saved": False}
    params = dict(result["parameters"])
    if source == "csv":
        params.pop("seed", None)
    if mode == MODE:
        params["mode"] = mode
    saving_started = time.perf_counter()
    try:
        async with asyncio.timeout(4):
            record = await repo.save_run(
                client_id=client_id,
                source=source,
                params=params,
                status="ok",
                result=result,
                duration_ms=duration_ms,
            )
            run_id = record["id"]
    except Exception as exc:
        logger.warning("Simulation save could not be confirmed (%s)", type(exc).__name__)
        return {"saved": False}

    pruning_started = time.perf_counter()
    try:
        async with asyncio.timeout(2):
            await repo.prune(client_id=client_id, keep=50)
    except Exception as exc:
        logger.warning("Simulation history prune failed (%s)", type(exc).__name__)
    if mode == MODE:
        logger.info(
            "Extended simulation persistence: save %.1f ms, prune %.1f ms",
            (pruning_started - saving_started) * 1000,
            (time.perf_counter() - pruning_started) * 1000,
        )
    return {"saved": True, "run_id": run_id}


async def execute_job(
    request: Request,
    settings: Settings,
    client_id: str,
    mode: ExperimentMode,
    parameters: dict,
    contents: bytes | None,
) -> Response:
    started = time.perf_counter()
    simulations = request.app.state.simulations
    services, steps = settings.simulation_caps(mode == MODE)
    encoded = await simulations.run(settings, mode, services, steps, parameters, contents)
    duration_ms = round((time.perf_counter() - started) * 1000)
    # Persist an ordinary decoded result for historical compatibility. Reuse the
    # worker's byte representation for the response instead of re-encoding traces.
    metadata = await persist_result(
        request,
        client_id,
        "simulated" if contents is None else "csv",
        mode,
        json.loads(encoded),
        duration_ms,
    )
    return Response(
        content=encoded[:-1] + b"," + json.dumps(metadata, separators=(",", ":")).encode()[1:],
        media_type="application/json",
    )


async def respond_to_simulation(
    request: Request,
    settings: Settings,
    client_id: str,
    mode: ExperimentMode,
    parameters: dict,
    file: UploadFile | None = None,
) -> Response:
    visitor = rate_limiter.extract_client_id(request)
    with request.app.state.simulations.admit(visitor):
        contents = None
        if file is not None:
            contents = await file.read(MAX_CSV_BYTES + 1)
            if len(contents) > MAX_CSV_BYTES:
                raise HTTPException(413, "Uploaded CSV exceeds the 5 MiB limit.")
        work = asyncio.create_task(
            execute_job(request, settings, client_id, mode, parameters, contents)
        )
        disconnect = asyncio.create_task(wait_for_disconnect(request))
        try:
            completed, _ = await asyncio.wait(
                (work, disconnect), return_when=asyncio.FIRST_COMPLETED
            )
            if work in completed:
                return work.result()
            disconnect.result()
            return Response(status_code=499)
        except HTTPException:
            raise
        except TimeoutError as exc:
            raise HTTPException(
                504,
                f"Simulation exceeded the {settings.worker_timeout_seconds}-second worker budget. "
                "Try a smaller workload.",
            ) from exc
        except Exception as exc:
            logger.error("Simulation failed (%s)", type(exc).__name__)
            raise HTTPException(500, "Simulation failed") from exc
        finally:
            work.cancel()
            disconnect.cancel()
            await asyncio.gather(work, disconnect, return_exceptions=True)


@router.post("/simulate", dependencies=[Depends(global_sim_limiter.check)])
async def simulate_workload(
    req: SimulateRequest,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    client_id: Annotated[str, Depends(verify_api_key)],
) -> Response:
    """Run a simulation on synthetic seeded workload across TIME and SERVICE splits."""
    require_extended_enabled(req.mode, settings, request)
    services, steps = settings.simulation_caps(req.mode == MODE)
    for name, value, cap in (
        ("n_services", req.n_services, services),
        ("n_steps", req.n_steps, steps),
    ):
        if value > cap:
            setting = "SIM_EXTENDED_MAX_" if req.mode == MODE else "SIM_MAX_"
            setting += name.removeprefix("n_").upper()
            raise HTTPException(422, f"Requested {name} ({value}) exceeds {setting} limit ({cap}).")
    return await respond_to_simulation(
        request, settings, client_id, req.mode, req.model_dump(exclude={"mode"})
    )


@router.post("/simulate/csv", dependencies=[Depends(global_sim_limiter.check)])
async def simulate_csv_workload(
    file: Annotated[UploadFile, File(...)],
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    client_id: Annotated[str, Depends(verify_api_key)],
    target_violation: float = Query(default=0.01, ge=0.005, le=0.05),
    form_target_violation: Annotated[
        float | None, Form(alias="target_violation", ge=0.005, le=0.05)
    ] = None,
    mode: Annotated[ExperimentMode, Form()] = "cpu-only",
) -> Response:
    """Execute an allocation experiment on an uploaded workload CSV."""
    require_extended_enabled(mode, settings, request)
    if form_target_violation is not None:
        target_violation = form_target_violation
    return await respond_to_simulation(
        request, settings, client_id, mode, {"seed": 42, "target_violation": target_violation}, file
    )
