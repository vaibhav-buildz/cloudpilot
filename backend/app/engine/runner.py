"""Master experiment runner executing TIME and SERVICE benchmark pipelines."""

from __future__ import annotations

import time
from typing import Any

import numpy as np

from app.engine.baselines import (
    compute_ewma_series,
    compute_rolling_max_48,
    compute_rolling_p99,
    compute_static_allocation,
    tune_ewma,
)
from app.engine.bootstrap import paired_bootstrap_test
from app.engine.evaluate import EvaluationMetrics, compute_metrics
from app.engine.features import MIN_HISTORY_REQUIRED, build_dataset
from app.engine.generator import WorkloadData, generate_workload
from app.engine.margins import SelectedMargin, apply_margin, select_margin
from app.engine.models import fit_model, get_model_instances


def _check_deadline(deadline: float, stage_name: str) -> None:
    if time.time() > deadline:
        raise TimeoutError(f"Experiment exceeded execution deadline during '{stage_name}'.")


def run_split_pipeline(
    demand: np.ndarray,
    static_requests: np.ndarray,
    train_services: np.ndarray,
    val_services: np.ndarray,
    test_services: np.ndarray,
    train_start: int,
    train_end: int,
    val_start: int,
    val_end: int,
    test_start: int,
    test_end: int,
    target_violation: float,
    deadline: float,
    n_estimators_override: int | None = None,
) -> dict[str, Any]:
    """Execute feature generation, training, validation margin tuning, and test evaluation."""
    _check_deadline(deadline, "feature building")

    # 1. Build train / val / test datasets for ML models
    X_train, y_train, srv_train, t_train = build_dataset(
        demand, train_start, train_end, train_services
    )
    X_val, y_val, srv_val, t_val = build_dataset(demand, val_start, val_end, val_services)
    X_test, y_test, srv_test, t_test = build_dataset(demand, test_start, test_end, test_services)

    static_val = static_requests[srv_val]
    static_test = static_requests[srv_test]

    # 2. Evaluate Baselines on Validation Split
    _check_deadline(deadline, "baseline tuning")

    baseline_val_preds: dict[str, np.ndarray] = {
        "static": compute_static_allocation(
            val_end - val_start, static_requests, val_services
        ).flatten(),
        "rolling_max_48": compute_rolling_max_48(
            demand, val_start, val_end, val_services
        ).flatten(),
        "rolling_p99": compute_rolling_p99(demand, val_start, val_end, val_services).flatten(),
    }

    best_alpha, ewma_val_margin = tune_ewma(
        demand, val_start, val_end, static_val, target_violation, val_services
    )
    baseline_val_preds["ewma"] = compute_ewma_series(
        demand, best_alpha, val_start, val_end, val_services
    ).flatten()

    # Determine baseline margins and select Comparator
    val_margins: dict[str, SelectedMargin | None] = {}
    val_metrics: dict[str, EvaluationMetrics] = {}

    for name in ["static", "rolling_max_48", "rolling_p99"]:
        preds = baseline_val_preds[name]
        if name == "static":
            margin = SelectedMargin("multiplicative", 1.00)
        else:
            margin = select_margin(y_val, preds, target_violation, static_val)
        val_margins[name] = margin

        if margin is not None:
            alloc = apply_margin(preds, margin.margin_type, margin.margin_value, static_val)
            val_metrics[name] = compute_metrics(
                y_val,
                alloc,
                static_val,
                target_violation,
                predictions=preds,
                service_indices=srv_val,
            )
        else:
            val_metrics[name] = EvaluationMetrics(
                violation_rate=float(np.mean(y_val > preds)),
                savings=0.0,
                utilization=0.0,
                wastage=0.0,
                is_feasible=False,
            )

    val_margins["ewma"] = ewma_val_margin
    if ewma_val_margin is not None:
        ewma_alloc = apply_margin(
            baseline_val_preds["ewma"],
            ewma_val_margin.margin_type,
            ewma_val_margin.margin_value,
            static_val,
        )
        val_metrics["ewma"] = compute_metrics(
            y_val,
            ewma_alloc,
            static_val,
            target_violation,
            predictions=baseline_val_preds["ewma"],
            service_indices=srv_val,
        )
    else:
        val_metrics["ewma"] = EvaluationMetrics(
            violation_rate=float(np.mean(y_val > baseline_val_preds["ewma"])),
            savings=0.0,
            utilization=0.0,
            wastage=0.0,
            is_feasible=False,
        )

    # Comparator: baseline with highest validation savings among feasible baselines
    feasible_baselines = [
        name for name, m in val_metrics.items() if m.is_feasible and val_margins[name] is not None
    ]
    if feasible_baselines:
        comparator_name = max(feasible_baselines, key=lambda n: val_metrics[n].savings)
    else:
        comparator_name = "static"

    # 3. Fit ML Models & Select Validation Margins
    _check_deadline(deadline, "model training")
    models = get_model_instances(n_estimators_override=n_estimators_override)
    test_preds: dict[str, np.ndarray] = {}

    for name, model in models.items():
        _check_deadline(deadline, f"training {name}")
        fit_model(model, X_train, y_train)

        # Validation prediction & margin tuning
        pred_val = model.predict(X_val)
        allow_zero = name == "GBR_q95"
        val_margins[name] = select_margin(
            y_val,
            pred_val,
            target_violation=target_violation,
            static_val=static_val,
            allow_zero_margin=allow_zero,
        )

        # Test prediction
        test_preds[name] = model.predict(X_test)

    # 4. Compute Test Predictions for Baselines
    baseline_test_preds: dict[str, np.ndarray] = {
        "static": compute_static_allocation(
            test_end - test_start, static_requests, test_services
        ).flatten(),
        "rolling_max_48": compute_rolling_max_48(
            demand, test_start, test_end, test_services
        ).flatten(),
        "rolling_p99": compute_rolling_p99(demand, test_start, test_end, test_services).flatten(),
        "ewma": compute_ewma_series(
            demand, best_alpha, test_start, test_end, test_services
        ).flatten(),
    }
    test_preds.update(baseline_test_preds)

    # 5. Evaluate all methods on Test Split over identical rows
    _check_deadline(deadline, "test evaluation")
    test_results: dict[str, dict[str, Any]] = {}

    for name in list(models.keys()) + ["static", "rolling_max_48", "rolling_p99", "ewma"]:
        preds = test_preds[name]
        margin = val_margins.get(name)

        if margin is not None:
            alloc = apply_margin(preds, margin.margin_type, margin.margin_value, static_test)
            metrics = compute_metrics(
                demand=y_test,
                allocation=alloc,
                static_requests=static_test,
                target_violation=target_violation,
                predictions=preds,
                service_indices=srv_test,
            )
            test_results[name] = {
                "violation_rate": metrics.violation_rate,
                "savings": metrics.savings,
                "utilization": metrics.utilization,
                "wastage": metrics.wastage,
                "is_feasible": metrics.is_feasible,
                "mae": metrics.mae,
                "rmse": metrics.rmse,
                "margin_type": margin.margin_type,
                "margin_value": margin.margin_value,
                "per_service_savings": metrics.per_service_savings,
            }
        else:
            test_results[name] = {
                "violation_rate": float(np.mean(y_test > preds)),
                "savings": 0.0,
                "utilization": 0.0,
                "wastage": 0.0,
                "is_feasible": False,
                "mae": None,
                "rmse": None,
                "margin_type": None,
                "margin_value": None,
                "per_service_savings": [0.0] * len(np.unique(srv_test)),
            }

    return {
        "comparator": comparator_name,
        "methods": test_results,
    }


def run_experiment(
    seed: int = 42,
    n_services: int = 12,
    n_steps: int = 1000,
    target_violation: float = 0.01,
    timeout_seconds: float = 60.0,
    workload: WorkloadData | None = None,
    n_estimators_override: int | None = None,
) -> dict[str, Any]:
    """Execute complete CloudPilot benchmark across TIME and SERVICE splits."""
    start_time = time.time()
    deadline = start_time + timeout_seconds

    if workload is None:
        workload = generate_workload(seed=seed, n_services=n_services, n_steps=n_steps)

    demand = workload.demand
    static_requests = workload.static_requests
    total_services, total_steps = demand.shape

    if total_steps < MIN_HISTORY_REQUIRED + 100:
        raise ValueError(
            f"Workload steps ({total_steps}) too short. "
            f"Must be at least {MIN_HISTORY_REQUIRED + 100}."
        )

    # -------------------------------------------------------------
    # 1. TIME SPLIT: Train (60%), Validation (15%), Test (25%)
    # -------------------------------------------------------------
    _check_deadline(deadline, "TIME split")
    train_end = int(0.60 * total_steps)
    val_end = int(0.75 * total_steps)
    test_end = total_steps

    all_services = np.arange(total_services)

    time_split_res = run_split_pipeline(
        demand=demand,
        static_requests=static_requests,
        train_services=all_services,
        val_services=all_services,
        test_services=all_services,
        train_start=MIN_HISTORY_REQUIRED,
        train_end=train_end,
        val_start=train_end,
        val_end=val_end,
        test_start=val_end,
        test_end=test_end,
        target_violation=target_violation,
        deadline=deadline,
        n_estimators_override=n_estimators_override,
    )

    # Hypothesis 1: GBR_q95 vs Comparator on TIME split
    comparator_time = time_split_res["comparator"]
    gbr_time = time_split_res["methods"]["GBR_q95"]
    comp_time = time_split_res["methods"][comparator_time]

    if gbr_time["is_feasible"] and comp_time["per_service_savings"] is not None:
        boot_h1 = paired_bootstrap_test(
            gbr_time["per_service_savings"],
            comp_time["per_service_savings"],
        )
        h1_verdict = "SUPPORTED" if boot_h1.ci_lower > 0.0 else "NOT_SUPPORTED"
    else:
        boot_h1 = paired_bootstrap_test([0.0] * total_services, [0.0] * total_services)
        h1_verdict = "NOT_SUPPORTED"

    # -------------------------------------------------------------
    # 2. SERVICE SPLIT: Train (60%), Validation (15%), Test (25%)
    # -------------------------------------------------------------
    _check_deadline(deadline, "SERVICE split")
    n_train_srv = max(1, int(0.60 * total_services))
    n_val_srv = max(1, int(0.15 * total_services))
    train_srv = all_services[:n_train_srv]
    val_srv = all_services[n_train_srv : n_train_srv + n_val_srv]
    test_srv = all_services[n_train_srv + n_val_srv :]

    if len(test_srv) == 0:
        test_srv = all_services[-1:]

    # For SERVICE split, use common observation steps [MIN_HISTORY_REQUIRED, total_steps]
    service_split_res = run_split_pipeline(
        demand=demand,
        static_requests=static_requests,
        train_services=train_srv,
        val_services=val_srv,
        test_services=test_srv,
        train_start=MIN_HISTORY_REQUIRED,
        train_end=total_steps,
        val_start=MIN_HISTORY_REQUIRED,
        val_end=total_steps,
        test_start=MIN_HISTORY_REQUIRED,
        test_end=total_steps,
        target_violation=target_violation,
        deadline=deadline,
        n_estimators_override=n_estimators_override,
    )

    # Hypothesis 2: Non-inferiority of GBR_q95 vs Comparator on SERVICE split within -1.0 pp
    comparator_srv = service_split_res["comparator"]
    gbr_srv = service_split_res["methods"]["GBR_q95"]
    comp_srv = service_split_res["methods"][comparator_srv]

    if gbr_srv["is_feasible"] and comp_srv["per_service_savings"] is not None:
        boot_h2 = paired_bootstrap_test(
            gbr_srv["per_service_savings"],
            comp_srv["per_service_savings"],
        )
        # Non-inferiority threshold: -1.0 pp (-0.01)
        h2_verdict = "SUPPORTED" if boot_h2.ci_lower > -0.01 else "NOT_SUPPORTED"
    else:
        boot_h2 = paired_bootstrap_test([0.0] * len(test_srv), [0.0] * len(test_srv))
        h2_verdict = "NOT_SUPPORTED"

    # Hypothesis 3: Feasibility (test pooled violation <= 1.5% on both splits)
    v_time = gbr_time["violation_rate"]
    v_srv = gbr_srv["violation_rate"]
    h3_supported = (v_time <= 0.015) and (v_srv <= 0.015)
    h3_verdict = "SUPPORTED" if h3_supported else "NOT_SUPPORTED"

    elapsed_seconds = round(time.time() - start_time, 2)

    return {
        "disclaimer": (
            "Results describe synthetic or uploaded workload data within the discrete simulation "
            "engine and do not model physical cloud infrastructure."
        ),
        "execution_time_seconds": elapsed_seconds,
        "parameters": {
            "seed": seed,
            "n_services": total_services,
            "n_steps": total_steps,
            "target_violation": target_violation,
        },
        "time_split": {
            "comparator": comparator_time,
            "methods": time_split_res["methods"],
            "h1": {
                "hypothesis": "H1: GBR_q95 has higher test savings than Comparator on TIME split",
                "verdict": h1_verdict,
                "estimate": boot_h1.estimate,
                "ci_lower": boot_h1.ci_lower,
                "ci_upper": boot_h1.ci_upper,
                "p_value": boot_h1.p_value,
            },
        },
        "service_split": {
            "comparator": comparator_srv,
            "methods": service_split_res["methods"],
            "h2": {
                "hypothesis": (
                    "H2: GBR_q95 non-inferior to Comparator within -1.0 pp on SERVICE split"
                ),
                "verdict": h2_verdict,
                "estimate": boot_h2.estimate,
                "ci_lower": boot_h2.ci_lower,
                "ci_upper": boot_h2.ci_upper,
                "p_value": boot_h2.p_value,
            },
        },
        "h3": {
            "hypothesis": "H3: Test pooled violation <= 1.5% on both TIME and SERVICE splits",
            "verdict": h3_verdict,
            "test_violation_time": v_time,
            "test_violation_service": v_srv,
            "threshold": 0.015,
        },
    }
