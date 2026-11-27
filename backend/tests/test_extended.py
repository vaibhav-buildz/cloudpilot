import json

import numpy as np
import pytest

from app.engine.extended import (
    causal_reference,
    offered_tasks,
    parse_extended_csv,
    run_extended,
    synthetic_memory,
)
from app.engine.generator import generate_workload
from app.engine.task_scheduler import IntervalUsage, Task, run_service, task_metrics
from app.ratelimit import global_sim_limiter


def test_deterministic_workload_and_causal_capacity():
    cpu = generate_workload(42, 4, 600).demand
    np.testing.assert_array_equal(cpu, generate_workload(42, 4, 600).demand)
    memory = synthetic_memory(cpu, 42)
    np.testing.assert_array_equal(memory, synthetic_memory(cpu, 42))
    assert np.ptp(memory / cpu) > 1
    altered = cpu.copy()
    altered[:, 288:] += 10000
    np.testing.assert_array_equal(causal_reference(cpu), causal_reference(altered))
    np.testing.assert_array_equal(memory[:, :288], synthetic_memory(altered, 42)[:, :288])


def test_fifo_wait_and_continuous_completion_release():
    tasks = [Task("b", 0, 0, 3, 2), Task("a", 0, 0, 4, 2), Task("c", 0, 10, 2, 2)]
    states, backlog = run_service(tasks, np.array([1, 1]), np.array([2, 2]), 10)
    by_id = {s.task.id: s for s in states}
    assert by_id["a"].start == 0 and by_id["a"].completion == 4
    assert by_id["b"].start == 4 and by_id["b"].completion == 7
    assert by_id["c"].start == 10 and by_id["c"].completion == 12
    assert backlog == [0, 0]
    metrics = task_metrics(states, backlog, 20)
    assert metrics["throughput_per_second"] == 3 / 20
    assert metrics["timing_seconds"]["waiting"]["mean"] == 4 / 3
    assert metrics["timing_seconds"]["response"]["median"] == 4
    assert metrics["timing_seconds"]["execution"]["median"] == 3


def test_cpu_sharing_and_memory_suspension_preserve_progress():
    tasks = [Task("a", 0, 0, 12, 1), Task("b", 0, 0, 12, 1)]
    states, backlog = run_service(tasks, np.array([2, 1, 2]), np.array([2, 0, 2]), 10)
    assert backlog == [0, 2, 0]
    assert [s.completion for s in states] == [22, 22]
    assert [s.remaining for s in states] == [0, 0]
    delayed, backlog = run_service(tasks, np.array([0, 1]), np.array([2, 0]), 10)
    assert all(s.start == 0 and s.first_service is None for s in delayed)
    metrics = task_metrics(delayed, backlog, 20)
    assert metrics["suspended_final"] == 2
    assert metrics["unfinished"] == 2 and metrics["completion_rate"] == 0
    assert metrics["timing_seconds"]["response"]["median"] is None
    delayed, _ = run_service([tasks[0]], np.array([0, 2]), np.array([1, 1]), 10)
    assert delayed[0].start == 0 and delayed[0].first_service == 10
    assert delayed[0].completion == 16


def test_queue_rejections_and_bad_arrivals():
    jobs = [Task("a", 0, 0, 1, 2), Task("b", 0, 0, 1, 1)]
    states, backlog = run_service(jobs, np.array([1]), np.array([1]), 10, queue_limit=1)
    assert backlog == [1]
    assert states[0].start is None and states[1].rejected
    assert task_metrics(states, backlog, 10)["unfinished"] == 2
    with pytest.raises(ValueError, match="grid-aligned"):
        run_service([Task("x", 0, 1, 1, 1)], np.array([1]), np.array([1]), 10)


def test_resource_accounting_across_memory_suspension_and_zero_cpu():
    tasks = [Task("a", 0, 0, 16, 2), Task("b", 0, 0, 12, 1)]
    cpu = np.array([2, 2, 0, 2])
    memory = np.array([3, 1, 2, 2])
    usage: list[IntervalUsage] = []
    states, backlog = run_service(tasks, cpu, memory, 10, usage=usage)
    assert usage == [
        IntervalUsage(20, 30),
        IntervalUsage(2, 1),
        IntervalUsage(0, 20),
        IntervalUsage(6, 6),
    ]
    assert [s.completion for s in states] == [33, 11]
    assert backlog == [0, 1, 0, 0]
    for interval, cpu_cap, memory_cap in zip(usage, cpu, memory, strict=True):
        assert 0 <= interval.cpu_core_seconds <= cpu_cap * 10
        assert 0 <= interval.memory_gib_seconds <= memory_cap * 10
    assert sum(row.cpu_core_seconds for row in usage) == sum(t.cpu_core_seconds for t in tasks)


def test_work_remaining_below_old_absolute_tolerance_is_not_completed_early():
    tasks = [Task("a", 0, 0, 1.0000000005, 1)]
    states, _ = run_service(tasks, np.array([1, 0]), np.array([1, 1]), 1)
    assert states[0].completion is None
    assert 0 < states[0].remaining < 1e-9


@pytest.mark.parametrize(
    ("split", "service", "start"), [("time_split", 0, 450), ("service_split", 3, 288)]
)
def test_held_out_mutation_leaves_validation_selection_unchanged(split, service, start):
    cpu = generate_workload(42, 4, 600).demand
    memory = synthetic_memory(cpu, 42)
    changed_cpu, changed_memory = cpu.copy(), memory.copy()
    changed_cpu[service, start:] *= 10
    changed_memory[service, start:] *= 10
    observed = [
        run_extended(workload=workload, n_estimators_override=2, diagnostics=False)[split]
        for workload in ((cpu, memory), (changed_cpu, changed_memory))
    ]
    baseline, changed = observed
    assert baseline["offered_tasks_sha256"] != changed["offered_tasks_sha256"]
    for resource in ("cpu", "memory"):
        assert baseline[resource]["comparator"] == changed[resource]["comparator"]
        for name, metrics in baseline[resource]["methods"].items():
            for field in ("margin_type", "margin_value", "is_feasible"):
                assert metrics[field] == changed[resource]["methods"][name][field]
    for name, policy in baseline["policies"].items():
        assert policy["jointly_feasible"] == changed["policies"][name]["jointly_feasible"]
        assert (
            policy["validation_joint_violation_rate"]
            == changed["policies"][name]["validation_joint_violation_rate"]
        )


def csv_data(edit=None):
    rows = ["service_id,timestamp,cpu_demand,memory_demand_gib"]
    for service in range(3):
        for step in range(482):
            fields = (service, step, step / 10, 3)
            if edit:
                fields = edit(*fields)
            rows.append(",".join(map(str, fields)))
    return "\n".join(rows).encode()


def test_extended_csv_alignment():
    cpu, memory = parse_extended_csv(csv_data())
    assert cpu.shape == memory.shape == (3, 482)
    assert cpu[0, -1] == 48.1 and memory[0, -1] == 3
    with pytest.raises(ValueError, match="same timestamp grid"):
        parse_extended_csv(csv_data(lambda s, t, c, m: (s, t + int(s == 2), c, m)))
    with pytest.raises(ValueError, match="duplicate"):
        parse_extended_csv(csv_data(lambda s, t, c, m: (s, min(t, 480), c, m)))
    with pytest.raises(ValueError, match="must be finite"):
        parse_extended_csv(csv_data(lambda s, t, c, m: (s, t, c, "nan")))
    with pytest.raises(ValueError, match="consecutive"):
        parse_extended_csv(csv_data(lambda s, t, c, m: (s, t + int(t >= 100), c, m)))


def test_joint_evaluation_and_payload():
    result = run_extended(n_estimators_override=2)
    assert len(json.dumps(result, allow_nan=False)) < 800_000
    for key, offered in (("time_split", 600), ("service_split", 312)):
        split = result[key]
        assert split["offered_tasks"] == offered
        assert len(split["offered_tasks_sha256"]) == 64
        assert len(split["memory"]["traces"][0]["steps"]) <= 96
        for method in ("LR", "DT", "RF", "GB", "GBR_q95"):
            metric = split["memory"]["methods"][method]
            assert metric["mae"] >= 0
            assert metric["mse"] == pytest.approx(metric["rmse"] ** 2)
        baseline = split["policies"]["static"]["tasks"]
        for name, policy in split["policies"].items():
            if not policy["jointly_feasible"] and name != "static":
                assert policy["tasks"] is None
            if policy["tasks"] is None:
                continue
            tasks = policy["tasks"]
            assert tasks["offered"] == offered
            assert tasks["completed"] + tasks["unfinished"] == offered
            for a, b in zip(tasks["task_samples"], baseline["task_samples"], strict=True):
                for field in ("id", "arrival_seconds", "cpu_core_seconds", "memory_gib"):
                    assert a[field] == b[field]
    with pytest.raises(ValueError, match="services"):
        run_extended(n_services=201)
    with pytest.raises(TimeoutError):
        run_extended(timeout_seconds=-1)
    tasks = offered_tasks(np.ones((2, 2)), np.ones((2, 2)), np.array([0, 1]), 0, 42)
    assert len({t.id for service in tasks for t in service}) == 4


@pytest.fixture
def isolated_sim_budget():
    global_sim_limiter.reset()
    yield
    global_sim_limiter.reset()


@pytest.mark.usefixtures("isolated_sim_budget")
def test_extended_routes_are_opt_in_and_keep_visitor_scoping(valid_dev_settings):
    from fastapi.testclient import TestClient

    from app.main import create_app
    from tests.conftest import TEST_VALID_KEY

    headers = {
        "X-API-Key": TEST_VALID_KEY,
        "X-Visitor-Id": "33333333-3333-4333-8333-333333333333",
    }
    experiment = {"mode": "extended-v1", "n_services": 3, "n_steps": 482}
    with TestClient(create_app(valid_dev_settings)) as client:
        assert client.post("/api/simulate", json=experiment).status_code == 401
        assert client.post("/api/simulate", headers=headers, json=experiment).status_code == 403
        assert client.get("/api/limits", headers=headers).json()["extended_max_steps"] is None

    settings = valid_dev_settings.model_copy(update={"ENABLE_EXTENDED_SIMULATION": True})
    assert not settings.model_copy(update={"APP_ENV": "production"}).extended_simulation_enabled
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/limits", headers=headers).json()["extended_max_steps"] == 600
        over_limit = client.post(
            "/api/simulate", headers=headers, json=experiment | {"n_services": 5}
        )
        assert over_limit.status_code == 422
        response = client.post(
            "/api/simulate/csv",
            headers=headers,
            data={"mode": "extended-v1"},
            files={"file": ("workload.csv", csv_data(), "text/csv")},
        )
        assert response.status_code == 200, response.text[:500]
        result = response.json()
        assert result["mode"] == "extended-v1" and result["saved"]
        path = f"/api/runs/{result['run_id']}"
        saved = client.get(path, headers=headers).json()
        assert saved["params"]["mode"] == "extended-v1"
        assert saved["result"]["time_split"] == result["time_split"]
        other = headers | {"X-Visitor-Id": "44444444-4444-4444-8444-444444444444"}
        assert client.get(path, headers=other).status_code == 404
        assert client.delete(path, headers=headers).status_code == 200


def test_production_extended_flag_has_independent_caps(valid_dev_settings):
    from fastapi.testclient import TestClient

    from app.main import create_app
    from tests.conftest import TEST_VALID_KEY

    settings = valid_dev_settings.model_copy(
        update={
            "APP_ENV": "production",
            "ALLOWED_ORIGIN": "https://example.com",
            "SUPABASE_URL": "https://example.com",
            "SUPABASE_SERVICE_KEY": "test-only",
            "SIM_MAX_SERVICES": 3,
            "ENABLE_PRODUCTION_EXTENDED_SIMULATION": True,
        }
    )
    with TestClient(create_app(settings)) as client:
        headers = {"X-API-Key": TEST_VALID_KEY}
        limits = client.get("/api/limits", headers=headers).json()
        assert limits["max_services"] == 3
        assert limits["extended_max_services"] == 4 and limits["extended_max_steps"] == 600
        assert (
            client.post(
                "/api/simulate",
                headers=headers,
                json={
                    "mode": "extended-v1",
                    "n_services": 5,
                    "n_steps": 600,
                },
            ).status_code
            == 422
        )
