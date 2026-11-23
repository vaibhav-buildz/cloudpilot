"""Evaluation metrics and identical-slice benchmarking."""

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
    per_service_savings: list[float] | None = None


def compute_metrics(
    demand: np.ndarray,
    allocation: np.ndarray,
    static_requests: np.ndarray,
    target_violation: float = 0.01,
    predictions: np.ndarray | None = None,
    service_indices: np.ndarray | None = None,
) -> EvaluationMetrics:
    """Compute benchmark metrics over identical evaluation rows.

    Parameters:
      demand: actual CPU demands (flat 1D array)
      allocation: allocated CPU capacity (flat 1D array matching demand)
      static_requests: static over-provisioned requests (flat 1D array matching demand)
      target_violation: maximum permissible violation threshold (default 1%)
      predictions: optional raw point predictions (for MAE / RMSE)
      service_indices: optional service index mapping for per-service savings
    """
    if len(demand) == 0:
        raise ValueError("Cannot evaluate metrics on empty data.")

    # 1. Operational violation rate
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

    # 5. Per-service savings for paired bootstrap
    per_service_savings: list[float] | None = None
    if service_indices is not None:
        unique_srvs = np.unique(service_indices)
        per_srv_list = []
        for srv in unique_srvs:
            mask = service_indices == srv
            s_alloc = np.sum(allocation[mask])
            s_static = np.sum(static_requests[mask])
            srv_save = 1.0 - (s_alloc / s_static) if s_static > 0 else 0.0
            per_srv_list.append(float(srv_save))
        per_service_savings = per_srv_list

    is_feasible = violation_rate <= target_violation

    return EvaluationMetrics(
        violation_rate=violation_rate,
        savings=savings,
        utilization=utilization,
        wastage=wastage,
        is_feasible=is_feasible,
        mae=mae,
        rmse=rmse,
        per_service_savings=per_service_savings,
    )
