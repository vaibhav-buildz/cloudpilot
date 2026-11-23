"""Pooled paired bootstrap statistical hypothesis testing across services."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

BOOTSTRAP_ROUNDS = 10_000
BOOTSTRAP_SEED = 42
CONFIDENCE_LEVEL = 0.95


@dataclass(frozen=True)
class BootstrapResult:
    """Outcome of pooled paired bootstrap hypothesis testing."""

    estimate: float  # Difference in pooled savings: savings(A) - savings(B)
    ci_lower: float  # Lower bound of 95% percentile CI
    ci_upper: float  # Upper bound of 95% percentile CI
    p_value: float  # Two-tailed empirical p-value
    n_resamples: int
    n_services: int


def paired_bootstrap_test(
    sum_a: list[float] | np.ndarray,
    sum_b: list[float] | np.ndarray,
    sum_static: list[float] | np.ndarray | None = None,
    n_resamples: int = BOOTSTRAP_ROUNDS,
    seed: int = BOOTSTRAP_SEED,
) -> BootstrapResult:
    """Execute pooled paired bootstrap resampling across services.

    Hypothesis test for fleet capacity difference:
      H0: pooled_savings(A) - pooled_savings(B) == 0

    For each resample of services (with replacement), aggregates total allocation
    and static capacity across the resampled fleet to compute pooled savings:
      savings(M) = 1 - sum(allocated_M) / sum(static)
      effect = savings(A) - savings(B) = (sum(allocated_B) - sum(allocated_A)) / sum(static)

    Guarantees:
      - Never receives or processes all-zero placeholder vectors.
      - 95% percentile confidence interval.
    """
    arr_a = np.asarray(sum_a, dtype=np.float64)
    arr_b = np.asarray(sum_b, dtype=np.float64)

    if len(arr_a) != len(arr_b):
        raise ValueError("Method allocations A and B must contain identical service counts.")

    n_services = len(arr_a)
    if n_services == 0:
        raise ValueError("Cannot perform bootstrap on empty service lists.")

    # Guard against dummy zero placeholders
    if np.all(arr_a == 0.0) and np.all(arr_b == 0.0):
        raise ValueError(
            "Bootstrap received an all-zero placeholder array. "
            "Methods must not be replaced by zeros."
        )

    rng = np.random.default_rng(seed)

    if sum_static is not None:
        arr_static = np.asarray(sum_static, dtype=np.float64)
        if len(arr_static) != n_services:
            raise ValueError("Static requests must have identical service count to allocations.")

        tot_static = float(np.sum(arr_static))
        tot_a = float(np.sum(arr_a))
        tot_b = float(np.sum(arr_b))
        point_estimate = float((tot_b - tot_a) / tot_static) if tot_static > 0 else 0.0

        # Vectorized resampling across service indices: shape (n_resamples, n_services)
        resample_idx = rng.choice(n_services, size=(n_resamples, n_services), replace=True)
        res_a = np.sum(arr_a[resample_idx], axis=1)
        res_b = np.sum(arr_b[resample_idx], axis=1)
        res_s = np.sum(arr_static[resample_idx], axis=1)

        # Avoid zero division if static request happens to sum to 0
        safe_s = np.where(res_s > 0, res_s, 1.0)
        resampled_effects = (res_b - res_a) / safe_s
    else:
        # Fallback when arrays are already normalized per-service savings
        diffs = arr_a - arr_b
        point_estimate = float(np.mean(diffs))

        resample_idx = rng.choice(n_services, size=(n_resamples, n_services), replace=True)
        resampled_effects = np.mean(diffs[resample_idx], axis=1)

    alpha = 1.0 - CONFIDENCE_LEVEL
    lower_pct = 100.0 * (alpha / 2.0)  # 2.5
    upper_pct = 100.0 * (1.0 - alpha / 2.0)  # 97.5

    ci_lower = float(np.percentile(resampled_effects, lower_pct))
    ci_upper = float(np.percentile(resampled_effects, upper_pct))

    # Two-tailed empirical p-value
    if point_estimate >= 0:
        p_val = 2.0 * float(np.mean(resampled_effects <= 0.0))
    else:
        p_val = 2.0 * float(np.mean(resampled_effects >= 0.0))
    p_val = min(1.0, max(0.0, p_val))

    return BootstrapResult(
        estimate=point_estimate,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        p_value=p_val,
        n_resamples=n_resamples,
        n_services=n_services,
    )
