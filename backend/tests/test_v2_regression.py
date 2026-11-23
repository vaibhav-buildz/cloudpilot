"""Regression tests verifying bug fixes for canonical layout, bootstrap, and feasibility."""

from __future__ import annotations

import numpy as np
import pytest

from app.engine.baselines import (
    compute_ewma_series,
    compute_rolling_max_48,
    compute_rolling_p99,
    compute_static_allocation,
)
from app.engine.bootstrap import paired_bootstrap_test
from app.engine.evaluate import compute_metrics
from app.engine.features import build_dataset
from app.engine.generator import generate_workload
from app.engine.runner import run_experiment


def test_static_allocation_zero_savings():
    """Static allocation must produce per-service savings == 0.0 and pooled savings == 0.0."""
    workload = generate_workload(seed=42, n_services=10, n_steps=600)
    demand = workload.demand
    static_requests = workload.static_requests
    n_steps = 100

    static_alloc_2d = compute_static_allocation(n_steps, static_requests)
    static_flat = static_alloc_2d.flatten()

    demand_slice = demand[:, 300 : 300 + n_steps]
    demand_flat = demand_slice.flatten()

    srv_indices = np.repeat(np.arange(10), n_steps)
    time_indices = np.tile(np.arange(300, 300 + n_steps), 10)

    # Static allocation evaluated against itself
    metrics = compute_metrics(
        demand=demand_flat,
        allocation=static_flat,
        static_requests=static_flat,
        service_indices=srv_indices,
        time_indices=time_indices,
    )

    # Pooled savings must be exactly 0
    assert metrics.savings == 0.0

    # Per-service savings must be exactly 0 for every service
    assert metrics.per_service_savings is not None
    assert len(metrics.per_service_savings) == 10
    for s_save in metrics.per_service_savings:
        assert s_save == 0.0


def test_pooled_savings_and_effects_bounds():
    """Pooled savings <= 1.0, and bootstrap effect between methods within [-1.0, +1.0]."""
    workload = generate_workload(seed=10, n_services=20, n_steps=800)
    n_steps = 200
    demand_slice = workload.demand[:, 400 : 400 + n_steps].flatten()
    static_flat = np.repeat(workload.static_requests, n_steps)
    srv_indices = np.repeat(np.arange(20), n_steps)

    alloc_a = compute_rolling_p99(workload.demand, 400, 400 + n_steps).flatten()
    alloc_b = compute_static_allocation(n_steps, workload.static_requests).flatten()

    metrics_a = compute_metrics(demand_slice, alloc_a, static_flat, service_indices=srv_indices)
    metrics_b = compute_metrics(demand_slice, alloc_b, static_flat, service_indices=srv_indices)

    assert metrics_a.savings <= 1.0
    assert metrics_b.savings <= 1.0

    boot = paired_bootstrap_test(
        metrics_a.per_service_sum_a,
        metrics_b.per_service_sum_a,
        metrics_a.per_service_sum_static,
        n_resamples=500,
        seed=42,
    )

    assert -1.0 <= boot.estimate <= 1.0
    assert -1.0 <= boot.ci_lower <= 1.0
    assert -1.0 <= boot.ci_upper <= 1.0


def test_baseline_2d_and_flattened_alignment():
    """Violations from 2D arrays must match flattened pipeline violations exactly."""
    workload = generate_workload(seed=7, n_services=8, n_steps=600)
    start_step, end_step = 300, 450
    n_steps = end_step - start_step

    # 1. Direct 2D evaluation for rolling max
    alloc_2d = compute_rolling_max_48(workload.demand, start_step, end_step)
    demand_2d = workload.demand[:, start_step:end_step]
    direct_violation = float(np.mean(demand_2d > alloc_2d))

    # 2. Pipeline flattened evaluation
    alloc_flat = alloc_2d.flatten()
    demand_flat = demand_2d.flatten()
    static_flat = np.repeat(workload.static_requests, n_steps)
    srv_idx = np.repeat(np.arange(8), n_steps)
    t_idx = np.tile(np.arange(start_step, end_step), 8)

    pipeline_metrics = compute_metrics(
        demand=demand_flat,
        allocation=alloc_flat,
        static_requests=static_flat,
        service_indices=srv_idx,
        time_indices=t_idx,
    )

    assert direct_violation == pipeline_metrics.violation_rate


def test_row_order_dataset_equals_baseline_allocations():
    """Row order of dataset must equal row order of baselines by (service_idx, time_idx)."""
    workload = generate_workload(seed=3, n_services=6, n_steps=500)
    start_step, end_step = 288, 388
    services = np.array([1, 3, 5])
    n_srv = len(services)
    n_steps = end_step - start_step

    X, y, srv_idx, t_idx = build_dataset(workload.demand, start_step, end_step, services)

    # Baseline 2D arrays flattened
    alloc_static = compute_static_allocation(n_steps, workload.static_requests, services).flatten()
    alloc_rmax = compute_rolling_max_48(workload.demand, start_step, end_step, services).flatten()
    alloc_rp99 = compute_rolling_p99(workload.demand, start_step, end_step, services).flatten()
    alloc_ewma = compute_ewma_series(workload.demand, 0.2, start_step, end_step, services).flatten()

    assert len(y) == n_srv * n_steps
    assert len(alloc_static) == len(y)
    assert len(alloc_rmax) == len(y)
    assert len(alloc_rp99) == len(y)
    assert len(alloc_ewma) == len(y)

    for i in range(len(y)):
        s = srv_idx[i]
        t = t_idx[i]
        assert y[i] == workload.demand[s, t]
        assert alloc_static[i] == workload.static_requests[s]


def test_bootstrap_never_receives_zeros_and_infeasible_yields_real_estimate():
    """Bootstrap rejects all-zero placeholders, and infeasible model yields empirical estimate."""
    with pytest.raises(ValueError, match="all-zero placeholder"):
        paired_bootstrap_test([0.0] * 10, [0.0] * 10)

    # When target is strict, model may be infeasible on validation; must yield real estimate
    res = run_experiment(
        seed=1,
        n_services=8,
        n_steps=600,
        target_violation=0.0001,
        n_estimators_override=5,
    )
    h1 = res["time_split"]["h1"]
    assert "estimate" in h1
    assert not (h1["estimate"] == 0.0 and h1["ci_lower"] == 0.0 and h1["ci_upper"] == 0.0)


def test_feasibility_depends_on_validation_only():
    """Feasibility flag is determined strictly from validation, not changed by test demand."""
    demand = np.array([10.0, 10.0, 10.0])
    alloc = np.array([5.0, 5.0, 5.0])  # 100% test violation
    static = np.array([20.0, 20.0, 20.0])

    # If is_feasible is passed as True (from validation), test evaluation preserves it as True
    m1 = compute_metrics(demand, alloc, static, is_feasible=True)
    assert m1.is_feasible is True
    assert m1.violation_rate == 1.0  # test violation reported separately

    # If is_feasible is passed as False, it remains False even with 0% test violation
    clean_alloc = np.array([15.0, 15.0, 15.0])  # 0% test violation
    m2 = compute_metrics(demand, clean_alloc, static, is_feasible=False)
    assert m2.is_feasible is False
    assert m2.violation_rate == 0.0
