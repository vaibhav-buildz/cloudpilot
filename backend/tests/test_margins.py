"""Tests for deterministic safety margin selection."""

from __future__ import annotations

import inspect

import numpy as np

from app.engine.margins import apply_margin, select_margin


def test_select_margin_picks_smallest_feasible():
    """select_margin must return the smallest margin on the grid achieving violation <= target."""
    actual = np.array([10.0, 10.0, 10.0, 10.0, 10.0])
    pred = np.array([8.0, 8.0, 8.0, 8.0, 8.0])  # Under-allocating by 2.0 (20%)

    # Target 0.0% violation -> requires allocation >= 10.0
    # For multiplicative: 8.0 * 1.25 = 10.0 -> margin 1.25
    margin = select_margin(actual, pred, target_violation=0.0)
    assert margin is not None
    assert margin.margin_type == "multiplicative"
    assert margin.margin_value == 1.25

    allocated = apply_margin(pred, margin.margin_type, margin.margin_value)
    assert np.mean(actual > allocated) <= 0.0


def test_select_margin_returns_none_when_infeasible():
    """Returns None when no grid value satisfies the violation constraint."""
    actual = np.array([100.0, 100.0, 100.0])
    pred = np.array([1.0, 1.0, 1.0])  # Severely under-predicting, 1.6x is only 1.6 cores

    margin = select_margin(actual, pred, target_violation=0.01)
    assert margin is None


def test_select_margin_invariant_to_row_order():
    """Shuffling rows must not change the selected margin."""
    rng = np.random.default_rng(42)
    actual = rng.uniform(10.0, 20.0, size=100)
    pred = actual * rng.uniform(0.85, 1.10, size=100)

    margin1 = select_margin(actual, pred, target_violation=0.01)

    perm = rng.permutation(100)
    margin2 = select_margin(actual[perm], pred[perm], target_violation=0.01)

    assert margin1 == margin2


def test_select_margin_never_accepts_test_data():
    """Function signature must accept validation data only, never test split data."""
    params = inspect.signature(select_margin).parameters
    param_names = list(params.keys())

    assert "y_val_actual" in param_names
    assert "y_val_pred" in param_names
    assert "test" not in "".join(param_names).lower()
