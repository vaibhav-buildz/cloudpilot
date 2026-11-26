"""Descriptive reporting, isolated from fitting and policy selection."""

import numpy as np

MAX_SERVICES = 6
MAX_POINTS = 96
HISTOGRAM_BINS = 16


def sample_indices(size: int, limit: int) -> np.ndarray:
    return np.linspace(0, size - 1, min(size, limit), dtype=int)


def statistics(values: np.ndarray) -> dict:
    p05, median, p95, p99 = np.percentile(values, [5, 50, 95, 99])
    return {
        "mean": float(np.mean(values)),
        "std_dev": float(np.std(values)),
        "min": float(np.min(values)),
        "max": float(np.max(values)),
        "median": float(median),
        "p05": float(p05),
        "p95": float(p95),
        "p99": float(p99),
    }


def describe_workload(demand: np.ndarray) -> dict:
    steps = sample_indices(demand.shape[1], MAX_POINTS)
    counts, edges = np.histogram(demand, bins=HISTOGRAM_BINS)
    peaks = demand.max(axis=1)
    # Keep the highest-peak services, breaking ties by canonical service order.
    services = np.argsort(-peaks, kind="stable")[:MAX_SERVICES]
    return {
        "statistics": statistics(demand),
        "histogram": {"edges": edges.tolist(), "counts": counts.tolist()},
        "steps": steps.tolist(),
        "mean_demand": demand[:, steps].mean(axis=0).tolist(),
        "peak_demand": demand[:, steps].max(axis=0).tolist(),
        "peak_step": int(np.unravel_index(np.argmax(demand), demand.shape)[1]),
        "services": [
            {"service_index": int(service), **statistics(demand[service])} for service in services
        ],
    }
