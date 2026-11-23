"""Evaluation metrics, canonical slice verification, and per-service accounting."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class EvaluationMetrics:
    """Summary metrics evaluated over identical service-time observations."""

    violation_rate: float
    savings: float
    utilization: float
    wastage: float
    is_feasible: bool
    mae: float | None = None
    rmse: float | None = None
    per_service_sum_a: list[float] | None = None
    per_service_sum_static: list[float] | None = None
    per_service_sum_demand: list[float] | None = None
    per_service_savings: list[float] | None = None


def compute_metrics(
    demand: np.ndarray,
    allocation: np.ndarray,
    static_requests: np.ndarray,
    target_violation: float = 0.01,
    predictions: np.ndarray | None = None,
    service_indices: np.ndarray | None = None,
    time_indices: np.ndarray | None = None,
    is_feasible: bool | None = None,
) -> EvaluationMetrics:
    """Compute benchmark metrics over identical evaluation observations.

    Guarantees canonical layout verification:
      Every allocation vector must have the exact same shape and ordering key as demand.

    Parameters:
      demand: actual CPU demands (flat 1D array)
      allocation: allocated CPU capacity (matching demand element-for-element)
      static_requests: static over-provisioned requests (matching demand element-for-element)
      target_violation: maximum permissible violation threshold (default 1%)
      predictions: optional raw point predictions (for MAE / RMSE)
      service_indices: service index array matching demand row-for-row
      time_indices: time step index array matching demand row-for-row
      is_feasible: validation-determined feasibility; if None, evaluated against target_violation
    """
    if len(demand) == 0:
        raise ValueError("Cannot evaluate metrics on empty data.")

    # Canonical layout assertion: shape and ordering key must match demand
    assert allocation.shape == demand.shape, (
        f"Allocation shape {allocation.shape} does not match demand shape {demand.shape}."
    )
    assert static_requests.shape == demand.shape, (
        f"Static requests shape {static_requests.shape} does not match demand shape {demand.shape}."
    )
    if predictions is not None:
        assert predictions.shape == demand.shape, (
            f"Predictions shape {predictions.shape} does not match demand shape {demand.shape}."
        )

    if service_indices is not None:
        assert len(service_indices) == len(demand), (
            f"Service indices ({len(service_indices)}) does not match demand ({len(demand)})."
        )
    if time_indices is not None:
        assert len(time_indices) == len(demand), (
            f"Time indices ({len(time_indices)}) does not match demand ({len(demand)})."
        )

    # 1. Operational violation rate on this slice
    violation_rate = float(np.mean(demand > allocation))

    # 2. Aggregate cost savings relative to static provisioning
    total_alloc = float(np.sum(allocation))
    total_static = float(np.sum(static_requests))
    savings = float(1.0 - total_alloc / total_static) if total_static > 0 else 0.0

    # 3. Resource utilization & wastage
    utilization = float(np.sum(demand) / total_alloc) if total_alloc > 0 else 0.0
    wastage_cores = np.maximum(allocation - demand, 0.0)
    wastage = float(np.sum(wastage_cores) / total_alloc) if total_alloc > 0 else 0.0

    # 4. Optional regression error metrics
    mae: float | None = None
    rmse: float | None = None
    if predictions is not None:
        errors = predictions - demand
        mae = float(np.mean(np.abs(errors)))
        rmse = float(np.sqrt(np.mean(errors**2)))

    # 5. Per-service accounting (sums and aligned ratios)
    per_service_sum_a: list[float] | None = None
    per_service_sum_static: list[float] | None = None
    per_service_sum_demand: list[float] | None = None
    per_service_savings: list[float] | None = None

    if service_indices is not None:
        unique_srvs = np.unique(service_indices)
        sum_a_list = []
        sum_static_list = []
        sum_demand_list = []
        per_srv_savings_list = []

        for srv in unique_srvs:
            mask = service_indices == srv
            s_alloc = float(np.sum(allocation[mask]))
            s_static = float(np.sum(static_requests[mask]))
            s_demand = float(np.sum(demand[mask]))

            sum_a_list.append(s_alloc)
            sum_static_list.append(s_static)
            sum_demand_list.append(s_demand)

            srv_save = 1.0 - (s_alloc / s_static) if s_static > 0 else 0.0
            per_srv_savings_list.append(float(srv_save))

        per_service_sum_a = sum_a_list
        per_service_sum_static = sum_static_list
        per_service_sum_demand = sum_demand_list
        per_service_savings = per_srv_savings_list

    # Feasibility: decided from validation only if provided; otherwise checked against target
    if is_feasible is None:
        feasible_flag = violation_rate <= target_violation
    else:
        feasible_flag = bool(is_feasible)

    return EvaluationMetrics(
        violation_rate=violation_rate,
        savings=savings,
        utilization=utilization,
        wastage=wastage,
        is_feasible=feasible_flag,
        mae=mae,
        rmse=rmse,
        per_service_sum_a=per_service_sum_a,
        per_service_sum_static=per_service_sum_static,
        per_service_sum_demand=per_service_sum_demand,
        per_service_savings=per_service_savings,
    )
