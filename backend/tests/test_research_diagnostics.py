import json
from pathlib import Path

import numpy as np
import pytest

from app.engine.csv_loader import load_workload_from_csv
from app.engine.diagnostics import MAX_POINTS, MAX_SERVICES
from app.engine.evaluate import compute_metrics
from app.engine.margins import apply_margin
from app.engine.runner import run_experiment

SAMPLE = Path(__file__).resolve().parents[2] / "frontend/public/sample-workload.csv"


def test_prediction_error_measures_raw_prediction():
    demand = np.array([2.0, 5.0])
    allocation = np.array([4.0, 6.0])
    predictions = np.array([1.0, 8.0])
    metrics = compute_metrics(demand, allocation, allocation, predictions=predictions)
    assert metrics.violation_rate == 0.0
    assert metrics.mae == 2.0
    assert metrics.mse == 5.0
    assert metrics.rmse == pytest.approx(np.sqrt(5))
    absent = compute_metrics(demand, allocation, allocation)
    assert absent.mae is absent.mse is absent.rmse is None


def test_bounded_reporting_aligns_samples_and_preserves_calculations():
    workload = load_workload_from_csv(SAMPLE.read_bytes())
    assert workload.demand.shape == (4, 600)
    original = run_experiment(workload=workload, n_estimators_override=2)
    result = run_experiment(workload=workload, n_estimators_override=2, include_diagnostics=True)

    assert sum(result["workload_analysis"]["histogram"]["counts"]) == 2400
    assert len(result["workload_analysis"]["steps"]) <= MAX_POINTS
    assert result["workload_analysis"]["statistics"]["max"] == workload.demand.max()
    assert len(json.dumps(result).encode()) < 512 * 1024
    assert result["h3"] == original["h3"]
    for key in ("time_split", "service_split"):
        split = result[key]
        assert {k: v for k, v in split.items() if k != "traces"} == original[key]
        assert 0 < len(split["traces"]) <= MAX_SERVICES
        for trace in split["traces"]:
            service = trace["service_index"]
            assert key == "time_split" or service >= 3
            steps = trace["steps"]
            assert len(steps) <= MAX_POINTS
            assert steps == sorted(set(steps))
            assert steps[0] == (450 if key == "time_split" else 288)
            assert steps[-1] == 599
            np.testing.assert_array_equal(trace["actual"], workload.demand[service, steps])
            assert trace["static_capacity"] == workload.static_requests[service]
            for name, values in trace["methods"].items():
                metrics = split["methods"][name]
                if name == "static":
                    assert values["predicted"] is None
                    continue
                assert len(values["predicted"]) == len(steps)
                if not metrics["is_feasible"]:
                    assert values["allocated"] is None
                else:
                    expected = apply_margin(
                        np.array(values["predicted"]),
                        metrics["margin_type"],
                        metrics["margin_value"],
                        np.full(len(steps), trace["static_capacity"]),
                    )
                    np.testing.assert_array_equal(values["allocated"], expected)


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"service_id,timestamp\na,0000\n", "cpu_demand"),
        (b"service_id,timestamp,cpu_demand\na,0,nan\n", "finite"),
        (b"service_id,timestamp,cpu_demand\na,0,-1\n", "negative"),
    ],
)
def test_invalid_csv(content, message):
    with pytest.raises(ValueError, match=message):
        load_workload_from_csv(content)


def test_duplicate_service_interval_is_rejected():
    with pytest.raises(ValueError, match="Duplicate timestamp"):
        load_workload_from_csv(SAMPLE.read_bytes() + b"service-1,0000,0.50\n")
