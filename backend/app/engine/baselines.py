"""Past-only heuristic baseline allocation policies."""

from __future__ import annotations

import numpy as np

from app.engine.margins import SelectedMargin, apply_margin, select_margin

STEPS_PER_DAY = 288
STEPS_PER_WEEK = 2016
EWMA_ALPHA_CANDIDATES = [0.1, 0.2, 0.3, 0.5]


def compute_static_allocation(
    n_steps: int,
    static_requests: np.ndarray,
    service_indices: list[int] | np.ndarray | None = None,
) -> np.ndarray:
    """Static reservation baseline: constant allocation matching per-service request.

    Returns array of shape (n_selected_services, n_steps).
    """
    if service_indices is not None:
        selected_static = static_requests[service_indices]
    else:
        selected_static = static_requests

    return np.repeat(selected_static[:, np.newaxis], n_steps, axis=1)


def compute_rolling_max_48(
    demand: np.ndarray,
    start_step: int,
    end_step: int,
    service_indices: list[int] | np.ndarray | None = None,
) -> np.ndarray:
    """Rolling maximum of the past 48 steps (past 4 hours).

    For each step t, takes max over indices [t - 48 : t].
    Returns array of shape (n_selected_services, end_step - start_step).
    """
    if start_step < 48:
        raise ValueError("Rolling max 48 requires start_step >= 48.")

    sel = slice(None) if service_indices is None else service_indices
    sub_demand = demand[sel]
    n_srv = sub_demand.shape[0]
    n_steps = end_step - start_step

    alloc = np.zeros((n_srv, n_steps), dtype=np.float64)
    for idx, t in enumerate(range(start_step, end_step)):
        alloc[:, idx] = np.max(sub_demand[:, t - 48 : t], axis=1)

    return alloc


def compute_rolling_p99(
    demand: np.ndarray,
    start_step: int,
    end_step: int,
    service_indices: list[int] | np.ndarray | None = None,
) -> np.ndarray:
    """Expanding p99 baseline with up to 7-day memory (min 1 day history).

    For each step t >= 288, evaluates percentile 99 over [max(0, t - 2016) : t].
    Returns array of shape (n_selected_services, end_step - start_step).
    """
    if start_step < STEPS_PER_DAY:
        raise ValueError(f"Rolling p99 requires start_step >= {STEPS_PER_DAY}.")

    sel = slice(None) if service_indices is None else service_indices
    sub_demand = demand[sel]
    n_srv = sub_demand.shape[0]
    n_steps = end_step - start_step

    alloc = np.zeros((n_srv, n_steps), dtype=np.float64)
    for idx, t in enumerate(range(start_step, end_step)):
        window_start = max(0, t - STEPS_PER_WEEK)
        window = sub_demand[:, window_start:t]
        alloc[:, idx] = np.percentile(window, 99, axis=1)

    return alloc


def compute_ewma_series(
    demand: np.ndarray,
    alpha: float,
    start_step: int,
    end_step: int,
    service_indices: list[int] | np.ndarray | None = None,
) -> np.ndarray:
    """Exponentially Weighted Moving Average baseline strictly shifted by 1 step.

    Allocation for time t is the EMA updated through t - 1.
    Returns array of shape (n_selected_services, end_step - start_step).
    """
    sel = slice(None) if service_indices is None else service_indices
    sub_demand = demand[sel]
    n_srv, total_steps = sub_demand.shape

    # Compute full cumulative EMA across time
    ema = np.zeros((n_srv, total_steps), dtype=np.float64)
    ema[:, 0] = sub_demand[:, 0]
    for step in range(1, total_steps):
        ema[:, step] = alpha * sub_demand[:, step] + (1.0 - alpha) * ema[:, step - 1]

    # Allocation at step t uses EMA through step t - 1
    # For t in range(start_step, end_step), slice ema[:, start_step - 1 : end_step - 1]
    alloc = ema[:, start_step - 1 : end_step - 1]
    return alloc


def tune_ewma(
    demand: np.ndarray,
    val_start: int,
    val_end: int,
    static_val: np.ndarray,
    target_violation: float = 0.01,
    service_indices: list[int] | np.ndarray | None = None,
) -> tuple[float, SelectedMargin | None]:
    """Select the best alpha and margin for EWMA on the validation set.

    Chooses the feasible alpha that maximizes validation savings.
    """
    sel = slice(None) if service_indices is None else service_indices
    y_val_actual = demand[sel, val_start:val_end].flatten()
    static_flat = static_val.flatten()

    best_alpha = EWMA_ALPHA_CANDIDATES[0]
    best_margin: SelectedMargin | None = None
    best_savings = -float("inf")

    for alpha in EWMA_ALPHA_CANDIDATES:
        preds = compute_ewma_series(demand, alpha, val_start, val_end, service_indices).flatten()
        margin = select_margin(
            y_val_actual=y_val_actual,
            y_val_pred=preds,
            target_violation=target_violation,
            static_val=static_flat,
        )
        if margin is not None:
            alloc = apply_margin(preds, margin.margin_type, margin.margin_value, static_flat)
            savings = 1.0 - float(np.sum(alloc) / np.sum(static_flat))
            if savings > best_savings:
                best_savings = savings
                best_alpha = alpha
                best_margin = margin

    return best_alpha, best_margin
