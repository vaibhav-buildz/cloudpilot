"""Synthetic workload generator for cloud CPU right-sizing simulation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Simulation timing constants
STEP_MINUTES = 5
STEPS_PER_HOUR = 60 // STEP_MINUTES  # 12
STEPS_PER_DAY = 24 * STEPS_PER_HOUR  # 288
STEPS_PER_WEEK = 7 * STEPS_PER_DAY  # 2016

# Workload generation parameter ranges
BASE_CPU_MIN = 2.0
BASE_CPU_MAX = 32.0

HARD_SERVICE_FRACTION = 0.30  # 30% of fleet has abrupt regime shifts and heavy bursts

BURST_PROB_STANDARD = 0.01
BURST_PROB_HARD = 0.04
BURST_DURATION_MIN = 2
BURST_DURATION_MAX = 6
BURST_MAGNITUDE_MIN = 1.5
BURST_MAGNITUDE_MAX = 3.5

NOISE_SIGMA_STANDARD = 0.08
NOISE_SIGMA_HARD = 0.25

STATIC_OVERPROVISION_BUFFER = 1.30  # Fixed static request = 1.3x 99th percentile


@dataclass(frozen=True)
class WorkloadData:
    """Container for multi-service workload time series and service metadata."""

    demand: np.ndarray  # Shape: (n_services, n_steps)
    static_requests: np.ndarray  # Shape: (n_services,)
    service_ids: list[str]
    group_ids: list[str]
    is_hard: np.ndarray  # Boolean mask of length n_services


def generate_workload(seed: int, n_services: int, n_steps: int) -> WorkloadData:
    """Generate a multi-service synthetic CPU workload with realistic components.

    Components:
    - Base allocation per service
    - Diurnal (daily) and weekly seasonality
    - Slow linear trend
    - Gaussian noise
    - Poisson-style burst arrivals
    - Regime shifts (step-level shifts) in hard services
    - Static over-provisioned allocation request per service
    """
    rng = np.random.default_rng(seed)

    service_ids = [f"srv-{i:03d}" for i in range(n_services)]
    groups = ["web-tier", "worker-queue", "api-gateway", "data-pipeline"]
    group_ids = [groups[i % len(groups)] for i in range(n_services)]

    # Determine which services are in the challenging/hard partition
    n_hard = int(np.ceil(n_services * HARD_SERVICE_FRACTION))
    hard_indices = set(rng.choice(n_services, size=n_hard, replace=False))
    is_hard = np.array([i in hard_indices for i in range(n_services)], dtype=bool)

    base_cpus = rng.uniform(BASE_CPU_MIN, BASE_CPU_MAX, size=n_services)
    demand = np.zeros((n_services, n_steps), dtype=np.float64)

    t_axis = np.arange(n_steps)
    daily_phase = 2.0 * np.pi * t_axis / STEPS_PER_DAY
    weekly_phase = 2.0 * np.pi * t_axis / STEPS_PER_WEEK

    for i in range(n_services):
        base = base_cpus[i]
        hard = is_hard[i]

        # Diurnal and weekly cyclic patterns
        daily_amp = rng.uniform(0.20, 0.40) * base
        weekly_amp = rng.uniform(0.10, 0.25) * base
        phase_shift = rng.uniform(0, 2.0 * np.pi)

        seasonality = daily_amp * np.sin(daily_phase + phase_shift) + weekly_amp * np.sin(
            weekly_phase
        )

        # Slow trend (-10% to +15% over the entire timeline)
        trend_slope = rng.uniform(-0.10, 0.15) * base / max(1, n_steps)
        trend = trend_slope * t_axis

        # Base series
        series = base + seasonality + trend

        # Noise component
        sigma = (NOISE_SIGMA_HARD if hard else NOISE_SIGMA_STANDARD) * base
        noise = rng.normal(0.0, sigma, size=n_steps)
        series += noise

        # Abrupt regime shifts (level change) for hard services
        if hard and n_steps > 100:
            n_shifts = rng.integers(1, 4)
            change_points = np.sort(rng.choice(np.arange(50, n_steps - 50), size=n_shifts))
            multiplier = 1.0
            for cp in change_points:
                multiplier *= rng.uniform(0.65, 1.50)
                series[cp:] += (multiplier - 1.0) * base * 0.5

        # Spikes / bursts
        burst_prob = BURST_PROB_HARD if hard else BURST_PROB_STANDARD
        burst_mask = rng.random(n_steps) < burst_prob
        burst_indices = np.where(burst_mask)[0]

        for b_idx in burst_indices:
            duration = rng.integers(BURST_DURATION_MIN, BURST_DURATION_MAX + 1)
            magnitude = rng.uniform(BURST_MAGNITUDE_MIN, BURST_MAGNITUDE_MAX) * base
            end_idx = min(n_steps, b_idx + duration)
            series[b_idx:end_idx] += magnitude

        # Ensure non-negative demand (minimum 0.05 CPU cores)
        demand[i, :] = np.maximum(series, 0.05)

    # Static request: fixed reservation based on conservative historical capacity
    static_requests = np.zeros(n_services, dtype=np.float64)
    for i in range(n_services):
        p99 = float(np.percentile(demand[i], 99))
        peak = float(np.max(demand[i]))
        static_requests[i] = max(p99 * STATIC_OVERPROVISION_BUFFER, peak * 1.05)

    return WorkloadData(
        demand=demand,
        static_requests=static_requests,
        service_ids=service_ids,
        group_ids=group_ids,
        is_hard=is_hard,
    )
