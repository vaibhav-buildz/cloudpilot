"""Regression anchors from the seed-42 pilot at 0070834."""

from hashlib import sha256

import numpy as np
import pytest
from threadpoolctl import threadpool_limits

from app.engine.extended import offered_tasks, run_extended, synthetic_memory
from app.engine.features import build_dataset, extract_features_at_t
from app.engine.generator import generate_workload
from app.engine.runner import run_experiment


def test_bulk_features_equal_past_only_reference_in_service_order():
    demand = generate_workload(42, 4, 600).demand
    services = [3, 1, 0]
    steps = range(288, 600)
    expected = np.stack([extract_features_at_t(demand, step)[services] for step in steps], axis=1)
    features, targets, service_ids, time_ids = build_dataset(demand, 288, 600, services)
    np.testing.assert_allclose(features, expected.reshape(features.shape), rtol=5e-15, atol=1e-15)
    np.testing.assert_array_equal(targets, demand[services, 288:600].ravel())
    np.testing.assert_array_equal(service_ids, np.repeat(services, len(steps)))
    np.testing.assert_array_equal(time_ids, np.tile(steps, len(services)))


def test_cpu_only_pilot_preserves_decisions_and_bootstrap():
    with threadpool_limits(limits=1):
        result = run_experiment(n_services=4, n_steps=600, rf_jobs=1)
    time, service = result["time_split"], result["service_split"]
    assert time["comparator"] == service["comparator"] == "rolling_max_48"
    assert time["methods"]["GBR_q95"]["violation_rate"] == 58 / 600
    assert service["methods"]["GBR_q95"]["violation_rate"] == 46 / 312
    assert time["h1"]["verdict"] == "NOT_SUPPORTED (infeasible on validation)"
    assert service["h2"]["verdict"] == "SUPPORTED"
    assert result["h3"]["verdict"] == "NOT_SUPPORTED"
    assert time["h1"]["ci_lower"] == pytest.approx(0.1558965879979812, abs=1e-10)
    assert service["h2"]["estimate"] == pytest.approx(0.3828457729251538, abs=1e-10)


def test_extended_pilot_preserves_task_arrivals_and_completions():
    with threadpool_limits(limits=1):
        result = run_extended(rf_jobs=1)
    cpu = generate_workload(42, 4, 600).demand
    memory = synthetic_memory(cpu, 42)
    for split, services, start, completions in (
        (
            "time_split",
            np.arange(4),
            450,
            {"GBR_q95": 600, "static": 600, "rolling_max_48": 600},
        ),
        (
            "service_split",
            np.array([3]),
            288,
            {"GB": 266, "GBR_q95": 312, "static": 312, "rolling_p99": 312},
        ),
    ):
        # Use the original digest construction with this platform's float representations.
        tasks = offered_tasks(cpu, memory, services, start, 42)
        expected = sha256("\n".join(repr(task) for group in tasks for task in group).encode())
        assert result[split]["offered_tasks_sha256"] == expected.hexdigest()
        policies = result[split]["policies"]
        assert {key for key, policy in policies.items() if policy["tasks"]} == completions.keys()
        for name, count in completions.items():
            assert policies[name]["tasks"]["completed"] == count
    assert result["service_split"]["policies"]["GBR_q95"]["test_joint_violation_rate"] == 51 / 312
