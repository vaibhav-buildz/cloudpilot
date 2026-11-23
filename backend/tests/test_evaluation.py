"""Tests for evaluation metrics and reporting completeness."""

from __future__ import annotations

import numpy as np

from app.engine.evaluate import compute_metrics


def test_compute_metrics_correctness():
    """Verify correct calculation of pooled violation, savings, utilization, and wastage."""
    demand = np.array([10.0, 12.0, 8.0, 15.0])
    alloc = np.array([12.0, 10.0, 10.0, 20.0])  # 1 violation (12 > 10 at index 1) -> 25% violation
    static = np.array([20.0, 20.0, 20.0, 20.0])  # total 80.0

    m = compute_metrics(
        demand=demand,
        allocation=alloc,
        static_requests=static,
        target_violation=0.01,
        predictions=alloc,
    )

    assert m.violation_rate == 0.25
    assert m.is_feasible is False
    assert m.savings == 1.0 - (52.0 / 80.0)  # 0.35 (35% savings)
    assert round(m.utilization, 4) == round(45.0 / 52.0, 4)
    assert m.mae is not None


def test_infeasible_model_reported_not_dropped():
    """An infeasible model must be explicitly reported as is_feasible=False."""
    demand = np.array([10.0, 20.0, 30.0])
    under_alloc = np.array([5.0, 5.0, 5.0])
    static = np.array([50.0, 50.0, 50.0])

    m = compute_metrics(demand, under_alloc, static, target_violation=0.01)
    assert m.is_feasible is False
    assert m.violation_rate == 1.0
