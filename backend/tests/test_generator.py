"""Tests for deterministic synthetic workload generation."""

from __future__ import annotations

import numpy as np

from app.engine.generator import generate_workload


def test_generator_deterministic_for_same_seed():
    """Generating with identical seed must yield identical demands and requests."""
    w1 = generate_workload(seed=42, n_services=5, n_steps=100)
    w2 = generate_workload(seed=42, n_services=5, n_steps=100)

    np.testing.assert_array_equal(w1.demand, w2.demand)
    np.testing.assert_array_equal(w1.static_requests, w2.static_requests)
    assert w1.service_ids == w2.service_ids


def test_generator_varies_with_different_seed():
    """Different seeds must yield distinct workload trajectories."""
    w1 = generate_workload(seed=42, n_services=5, n_steps=100)
    w2 = generate_workload(seed=99, n_services=5, n_steps=100)

    assert not np.array_equal(w1.demand, w2.demand)
    assert not np.array_equal(w1.static_requests, w2.static_requests)


def test_generator_shapes_and_bounds():
    """Generated arrays must match requested dimensions and uphold sanity bounds."""
    n_services = 6
    n_steps = 350
    w = generate_workload(seed=123, n_services=n_services, n_steps=n_steps)

    assert w.demand.shape == (n_services, n_steps)
    assert len(w.static_requests) == n_services
    assert len(w.service_ids) == n_services
    assert len(w.group_ids) == n_services
    assert len(w.is_hard) == n_services

    # Demand must be strictly positive
    assert np.all(w.demand >= 0.05)

    # Static request must exceed peak observed demand
    for i in range(n_services):
        assert w.static_requests[i] >= np.max(w.demand[i])
