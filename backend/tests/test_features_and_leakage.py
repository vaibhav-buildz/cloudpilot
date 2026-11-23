"""Tests verifying past-only features and strictly zero future data leakage."""

from __future__ import annotations

import numpy as np

from app.engine.baselines import (
    compute_ewma_series,
    compute_rolling_max_48,
    compute_rolling_p99,
)
from app.engine.features import extract_features_at_t
from app.engine.generator import generate_workload


def test_features_at_t_unaffected_by_future_perturbations():
    """Perturbing demand values at indices >= t must not alter extracted features at step t."""
    w = generate_workload(seed=42, n_services=4, n_steps=500)
    t = 350

    features_orig = extract_features_at_t(w.demand, t)

    # Perturb every value from index t onwards with extreme values
    corrupted_demand = w.demand.copy()
    corrupted_demand[:, t:] = 99999.0

    features_corrupted = extract_features_at_t(corrupted_demand, t)

    np.testing.assert_allclose(
        features_orig,
        features_corrupted,
        err_msg="Future data leakage detected in feature extraction at step t!",
    )


def test_rolling_max_48_unaffected_by_future_perturbations():
    """Rolling max 48 at step t must not touch values at >= t."""
    w = generate_workload(seed=42, n_services=3, n_steps=500)
    t = 300

    alloc_orig = compute_rolling_max_48(w.demand, t, t + 1)

    corrupted_demand = w.demand.copy()
    corrupted_demand[:, t:] = 88888.0

    alloc_corrupted = compute_rolling_max_48(corrupted_demand, t, t + 1)
    np.testing.assert_allclose(alloc_orig, alloc_corrupted)


def test_rolling_p99_unaffected_by_future_perturbations():
    """Rolling p99 at step t must not touch values at >= t."""
    w = generate_workload(seed=42, n_services=3, n_steps=500)
    t = 300

    alloc_orig = compute_rolling_p99(w.demand, t, t + 1)

    corrupted_demand = w.demand.copy()
    corrupted_demand[:, t:] = 77777.0

    alloc_corrupted = compute_rolling_p99(corrupted_demand, t, t + 1)
    np.testing.assert_allclose(alloc_orig, alloc_corrupted)


def test_ewma_unaffected_by_future_perturbations():
    """EWMA allocation at step t must not touch values at >= t."""
    w = generate_workload(seed=42, n_services=3, n_steps=500)
    t = 300

    alloc_orig = compute_ewma_series(w.demand, alpha=0.2, start_step=t, end_step=t + 1)

    corrupted_demand = w.demand.copy()
    corrupted_demand[:, t:] = 66666.0

    alloc_corrupted = compute_ewma_series(corrupted_demand, alpha=0.2, start_step=t, end_step=t + 1)
    np.testing.assert_allclose(alloc_orig, alloc_corrupted)
