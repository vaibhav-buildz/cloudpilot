"""Paired bootstrap statistical hypothesis testing across services."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

BOOTSTRAP_ROUNDS = 10_000
BOOTSTRAP_SEED = 42
CONFIDENCE_LEVEL = 0.95


@dataclass(frozen=True)
class BootstrapResult:
    """Outcome of paired bootstrap hypothesis testing."""

    estimate: float  # Mean difference in savings: savings(A) - savings(B)
    ci_lower: float  # Lower bound of 95% percentile CI
    ci_upper: float  # Upper bound of 95% percentile CI
    p_value: float  # Two-tailed empirical p-value
    n_resamples: int
    n_services: int


def paired_bootstrap_test(
    savings_a: list[float] | np.ndarray,
    savings_b: list[float] | np.ndarray,
    n_resamples: int = BOOTSTRAP_ROUNDS,
    seed: int = BOOTSTRAP_SEED,
) -> BootstrapResult:
    """Execute paired bootstrap resampling across services.

    H0: mean(savings_a - savings_b) == 0
    Computes 95% percentile confidence interval.
    """
    arr_a = np.asarray(savings_a, dtype=np.float64)
    arr_b = np.asarray(savings_b, dtype=np.float64)

    if len(arr_a) != len(arr_b):
        raise ValueError("savings_a and savings_b must contain identical service counts.")

    n_services = len(arr_a)
    if n_services == 0:
        raise ValueError("Cannot perform bootstrap on empty service lists.")

    diffs = arr_a - arr_b
    mean_diff = float(np.mean(diffs))

    rng = np.random.default_rng(seed)

    # Matrix resampling of service indices: shape (n_resamples, n_services)
    resample_idx = rng.choice(n_services, size=(n_resamples, n_services), replace=True)
    resampled_means = np.mean(diffs[resample_idx], axis=1)

    alpha = 1.0 - CONFIDENCE_LEVEL
    lower_pct = 100.0 * (alpha / 2.0)  # 2.5
    upper_pct = 100.0 * (1.0 - alpha / 2.0)  # 97.5

    ci_lower = float(np.percentile(resampled_means, lower_pct))
    ci_upper = float(np.percentile(resampled_means, upper_pct))

    # Two-tailed empirical p-value
    if mean_diff >= 0:
        p_val = 2.0 * float(np.mean(resampled_means <= 0.0))
    else:
        p_val = 2.0 * float(np.mean(resampled_means >= 0.0))
    p_val = min(1.0, max(0.0, p_val))

    return BootstrapResult(
        estimate=mean_diff,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        p_value=p_val,
        n_resamples=n_resamples,
        n_services=n_services,
    )
