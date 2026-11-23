"""Tests for paired bootstrap statistical hypothesis testing."""

from __future__ import annotations

import numpy as np

from app.engine.bootstrap import paired_bootstrap_test


def test_bootstrap_constant_two_percentage_point_effect():
    """A constant +0.02 (+2.0 pp) advantage must yield estimate 0.02 with CI strictly > 0."""
    n_services = 20
    # Method A has constant 0.22 savings, Method B has constant 0.20 savings
    savings_a = np.full(n_services, 0.22)
    savings_b = np.full(n_services, 0.20)

    res = paired_bootstrap_test(savings_a, savings_b, n_resamples=1000, seed=42)

    assert round(res.estimate, 4) == 0.02
    assert res.ci_lower > 0.0
    assert res.ci_upper > 0.0
    assert res.ci_lower <= res.estimate <= res.ci_upper


def test_bootstrap_identical_allocations():
    """Identical allocations must produce estimate 0.0 with CI containing 0."""
    n_services = 15
    savings_a = np.full(n_services, 0.25)
    savings_b = np.full(n_services, 0.25)

    res = paired_bootstrap_test(savings_a, savings_b, n_resamples=1000, seed=42)

    assert res.estimate == 0.0
    assert res.ci_lower <= 0.0 <= res.ci_upper


def test_bootstrap_deterministic_seed():
    """Identical seed must yield identical bootstrap estimates and intervals."""
    rng = np.random.default_rng(101)
    a = rng.uniform(0.1, 0.4, size=15)
    b = rng.uniform(0.1, 0.4, size=15)

    res1 = paired_bootstrap_test(a, b, n_resamples=1000, seed=42)
    res2 = paired_bootstrap_test(a, b, n_resamples=1000, seed=42)

    assert res1.estimate == res2.estimate
    assert res1.ci_lower == res2.ci_lower
    assert res1.ci_upper == res2.ci_upper
    assert res1.p_value == res2.p_value
