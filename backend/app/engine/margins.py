"""Safety margin grid definition, application, and deterministic selection."""

from __future__ import annotations

from typing import NamedTuple

import numpy as np


class SelectedMargin(NamedTuple):
    margin_type: str  # "multiplicative" or "additive"
    margin_value: float


# Fixed evaluation grids
MULTIPLICATIVE_GRID: list[float] = [round(1.00 + 0.01 * k, 2) for k in range(61)]  # 1.00 to 1.60
ADDITIVE_PP_GRID: list[float] = [round(0.0 + 0.5 * k, 1) for k in range(61)]  # 0.0 to 30.0 pp


def apply_margin(
    predictions: np.ndarray,
    margin_type: str,
    margin_value: float,
    static_requests: np.ndarray | None = None,
) -> np.ndarray:
    """Apply safety margin to raw predictions.

    - Multiplicative: A = pred * margin_value
    - Additive: A = pred + (margin_value / 100.0) * static_request
      (or pred + margin_value if static absent)
    """
    if margin_type == "multiplicative":
        return predictions * margin_value
    if margin_type == "additive":
        if static_requests is not None:
            return predictions + (margin_value / 100.0) * static_requests
        return predictions + margin_value
    raise ValueError(
        f"Unknown margin_type: '{margin_type}'. Expected 'multiplicative' or 'additive'."
    )


def select_margin(
    y_val_actual: np.ndarray,
    y_val_pred: np.ndarray,
    target_violation: float = 0.01,
    static_val: np.ndarray | None = None,
    allow_zero_margin: bool = False,
) -> SelectedMargin | None:
    """Deterministic selection of the smallest margin whose pooled validation violation <= target.

    Iterates through candidate margins from smallest to largest overhead.
    Returns:
      SelectedMargin if a feasible margin is found on the grid, else None (infeasible).

    Note: Test data must NEVER be passed to this function.
    """
    if len(y_val_actual) == 0:
        return None

    # Candidate evaluation order:
    # 1. Multiplicative margins starting at 1.00 (or zero-overhead baseline)
    # 2. Additive margins from 0.0 pp upwards
    candidates: list[tuple[str, float]] = []

    if allow_zero_margin:
        # Check if raw predictions already satisfy the target violation
        if np.mean(y_val_actual > y_val_pred) <= target_violation:
            return SelectedMargin("multiplicative", 1.00)

    for m in MULTIPLICATIVE_GRID:
        candidates.append(("multiplicative", m))

    for m in ADDITIVE_PP_GRID:
        candidates.append(("additive", m))

    # Evaluate each margin deterministically
    best_margin: SelectedMargin | None = None

    for m_type, m_val in candidates:
        allocated = apply_margin(y_val_pred, m_type, m_val, static_val)
        violation_rate = float(np.mean(y_val_actual > allocated))
        if violation_rate <= target_violation:
            best_margin = SelectedMargin(m_type, m_val)
            break

    return best_margin
