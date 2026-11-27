"""Past-only feature extraction for workload demand prediction."""

from __future__ import annotations

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from app.workload_limits import MIN_HISTORY_REQUIRED as MIN_HISTORY_REQUIRED
from app.workload_limits import MIN_WORKLOAD_SERVICES as MIN_WORKLOAD_SERVICES
from app.workload_limits import MIN_WORKLOAD_STEPS as MIN_WORKLOAD_STEPS
from app.workload_limits import TIME_TRAIN_FRACTION as TIME_TRAIN_FRACTION

LAGS = [1, 2, 3, 6, 12, 288]
ROLLING_WINDOWS = [12, 48]
STEPS_PER_DAY = 288

FEATURE_NAMES = [
    "lag_1",
    "lag_2",
    "lag_3",
    "lag_6",
    "lag_12",
    "lag_288",
    "rolling_mean_12",
    "rolling_max_12",
    "rolling_std_12",
    "rolling_mean_48",
    "rolling_max_48",
    "rolling_std_48",
    "tod_sin",
    "tod_cos",
]


def extract_features_at_t(demand: np.ndarray, t: int) -> np.ndarray:
    """Extract past-only features for all services at time step t.

    Input:
      demand: array of shape (n_services, n_steps)
      t: target time step (must be >= MIN_HISTORY_REQUIRED)

    Returns:
      features: array of shape (n_services, len(FEATURE_NAMES))
      Strict shift-before-rolling guarantee: values at indices >= t are never touched.
    """
    if t < MIN_HISTORY_REQUIRED:
        raise ValueError(
            f"Cannot extract features at step {t} < "
            f"minimum required history ({MIN_HISTORY_REQUIRED})."
        )

    n_services = demand.shape[0]
    features_list = []

    # 1. Past lag values (strictly tau < t)
    for lag in LAGS:
        features_list.append(demand[:, t - lag])

    # 2. Rolling statistics strictly over past windows [t - window : t]
    for w in ROLLING_WINDOWS:
        window_slice = demand[:, t - w : t]  # Slices indices t - w up to t - 1
        features_list.append(np.mean(window_slice, axis=1))
        features_list.append(np.max(window_slice, axis=1))
        features_list.append(np.std(window_slice, axis=1))

    # 3. Cyclical time-of-day features for step t
    tod_rad = 2.0 * np.pi * (t % STEPS_PER_DAY) / STEPS_PER_DAY
    tod_sin = np.full(n_services, np.sin(tod_rad), dtype=np.float64)
    tod_cos = np.full(n_services, np.cos(tod_rad), dtype=np.float64)
    features_list.extend([tod_sin, tod_cos])

    return np.column_stack(features_list)


def build_dataset(
    demand: np.ndarray,
    start_step: int = MIN_HISTORY_REQUIRED,
    end_step: int | None = None,
    service_indices: list[int] | np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Build matrix of past-only features X and target demand y across time steps.

    Canonical layout guarantee:
      Rows are organized in service-major order: service_idx outer, time_idx inner.
      Row i corresponds to service service_idx[i] and time step time_idx[i].
      y matches demand[selected_services, start_step:end_step].flatten() row for row.

    Returns:
      X: shape (n_samples, n_features)
      y: shape (n_samples,) representing actual demand at time t
      srv_idx: shape (n_samples,) service index for each sample
      t_idx: shape (n_samples,) time step index for each sample
    """
    total_services, total_steps = demand.shape
    if end_step is None:
        end_step = total_steps

    if service_indices is None:
        selected_services = np.arange(total_services)
    else:
        selected_services = np.array(service_indices, dtype=int)

    n_srv = len(selected_services)
    n_t = end_step - start_step
    if n_t <= 0 or n_srv <= 0:
        return (
            np.empty((0, len(FEATURE_NAMES))),
            np.empty(0),
            np.empty(0, dtype=int),
            np.empty(0, dtype=int),
        )

    if start_step < MIN_HISTORY_REQUIRED:
        raise ValueError(f"Dataset requires at least {MIN_HISTORY_REQUIRED} steps of history.")
    if end_step > total_steps:
        raise ValueError("Dataset ends beyond the available workload.")

    times = np.arange(start_step, end_step)
    radians = 2.0 * np.pi * (times % STEPS_PER_DAY) / STEPS_PER_DAY
    features = np.empty((n_srv, n_t, len(FEATURE_NAMES)), dtype=np.result_type(demand, float))
    features[:, :, -2] = np.sin(radians)
    features[:, :, -1] = np.cos(radians)
    for service, rows in zip(selected_services, features, strict=True):
        history = demand[service]
        for column, lag in enumerate(LAGS):
            rows[:, column] = history[start_step - lag : end_step - lag]
        # A window is a view, and the std temporary is bounded to one service.
        for index, window in enumerate(ROLLING_WINDOWS):
            windows = sliding_window_view(history[start_step - window : end_step - 1], window)
            column = len(LAGS) + 3 * index
            rows[:, column] = windows.mean(axis=1)
            rows[:, column + 1] = windows.max(axis=1)
            rows[:, column + 2] = windows.std(axis=1)

    X = features.reshape(n_srv * n_t, len(FEATURE_NAMES))
    y = demand[selected_services, start_step:end_step].reshape(-1)

    srv_idx = np.repeat(selected_services, n_t)
    t_idx = np.tile(times, n_srv)

    return X, y, srv_idx, t_idx
