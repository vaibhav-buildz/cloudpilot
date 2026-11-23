"""Past-only feature extraction for workload demand prediction."""

from __future__ import annotations

import numpy as np

LAGS = [1, 2, 3, 6, 12, 288]
ROLLING_WINDOWS = [12, 48]
MIN_HISTORY_REQUIRED = 288
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

    all_X = []
    all_y = []
    all_srv = []
    all_t = []

    for t in range(start_step, end_step):
        X_t = extract_features_at_t(demand, t)  # Shape (total_services, n_features)
        y_t = demand[:, t]

        # Filter by selected services
        all_X.append(X_t[selected_services])
        all_y.append(y_t[selected_services])
        all_srv.append(selected_services)
        all_t.append(np.full(n_srv, t, dtype=int))

    return (
        np.vstack(all_X),
        np.concatenate(all_y),
        np.concatenate(all_srv),
        np.concatenate(all_t),
    )
