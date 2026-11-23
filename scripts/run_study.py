"""Execute 10-seed simulation study and generate summary reports."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

# Ensure backend package is in python path
REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import numpy as np  # noqa: E402

from app.engine.bootstrap import paired_bootstrap_test  # noqa: E402
from app.engine.runner import run_experiment  # noqa: E402


def _format_p_value(p: float) -> str:
    """Format p-value: never print 0.0000; print '< 0.0001' when below 1/10000."""
    if p < 0.0001:
        return "< 0.0001"
    return f"{p:.4f}"


def generate_results_markdown(summary: dict[str, Any]) -> str:
    """Generate human-readable Markdown report for docs/results.md."""
    h1 = summary["headline"]["h1"]
    h2 = summary["headline"]["h2"]
    h3 = summary["headline"]["h3"]

    lines = [
        "# CloudPilot 10-Seed Simulation Study Results",
        "",
        "> **Simulated data. Results describe the simulator, not real clouds.**",
        "",
        "## 1. Headline Findings",
        "",
        f"- **H1 (TIME Split, Superiority)**: **{h1['verdict']}** "
        f"({h1['support_count']}/{h1['total_seeds']} seeds supported).  ",
        f"  - Median savings advantage over Comparator: **{h1['median_effect_pp']:+.2f} pp** "
        f"(95% median CI: [{h1['median_ci_lower_pp']:+.2f} pp, {h1['median_ci_upper_pp']:+.2f} pp]).  ",
        f"  - Secondary pooled paired bootstrap: **{h1['pooled_effect_pp']:+.2f} pp** "
        f"(95% CI: [{h1['pooled_ci_lower_pp']:+.2f} pp, {h1['pooled_ci_upper_pp']:+.2f} pp], "
        f"p {'' if _format_p_value(h1['pooled_p_value']).startswith('<') else '= '}{_format_p_value(h1['pooled_p_value'])}).",
        "",
        f"- **H2 (SERVICE Split, Non-Inferiority)**: **{h2['verdict']}** "
        f"({h2['support_count']}/{h2['total_seeds']} seeds supported within -1.0 pp margin).  ",
        f"  - Median savings difference on unseen services: **{h2['median_effect_pp']:+.2f} pp** "
        f"(95% median CI: [{h2['median_ci_lower_pp']:+.2f} pp, {h2['median_ci_upper_pp']:+.2f} pp]).  ",
        f"  - Secondary pooled paired bootstrap: **{h2['pooled_effect_pp']:+.2f} pp** "
        f"(95% CI: [{h2['pooled_ci_lower_pp']:+.2f} pp, {h2['pooled_ci_upper_pp']:+.2f} pp], "
        f"p {'' if _format_p_value(h2['pooled_p_value']).startswith('<') else '= '}{_format_p_value(h2['pooled_p_value'])}).",
        "",
        f"- **H3 (Operational Feasibility)**: **{h3['verdict']}** "
        f"({h3['support_count']}/{h3['total_seeds']} seeds supported with $\\le 1.5\\%$ violation).  ",
        f"  - Max test violation on TIME split: **{h3['max_test_violation_time'] * 100:.2f}%**.  ",
        f"  - Max test violation on SERVICE split: **{h3['max_test_violation_service'] * 100:.2f}%**.",
        "",
        "---",
        "",
        "## 2. Average Performance by Allocation Policy (TIME Split)",
        "",
        "| Policy | Category | Savings (%) | Violation (%) | Utilization (%) | Wastage (%) | Feasible Seeds |",
        "| :--- | :--- | :---: | :---: | :---: | :---: | :---: |",
    ]

    for m in summary["methods_summary_time"]:
        lines.append(
            f"| `{m['name']}` | {m['category']} | {m['savings_pct']:.2f}% | "
            f"{m['violation_pct']:.2f}% | {m['utilization_pct']:.2f}% | "
            f"{m['wastage_pct']:.2f}% | {m['feasible_count']}/10 |"
        )

    lines.extend(
        [
            "",
            "---",
            "",
            "## 3. Average Performance on Unseen Services (SERVICE Split)",
            "",
            "| Policy | Category | Savings (%) | Violation (%) | Utilization (%) | Wastage (%) | Feasible Seeds |",
            "| :--- | :--- | :---: | :---: | :---: | :---: | :---: |",
        ]
    )

    for m in summary["methods_summary_service"]:
        lines.append(
            f"| `{m['name']}` | {m['category']} | {m['savings_pct']:.2f}% | "
            f"{m['violation_pct']:.2f}% | {m['utilization_pct']:.2f}% | "
            f"{m['wastage_pct']:.2f}% | {m['feasible_count']}/10 |"
        )

    lines.extend(
        [
            "",
            "---",
            "",
            "## 4. Per-Seed Detailed Breakdown",
            "",
            "| Seed | TIME Comp | H1 Verdict | H1 Effect (CI) | SERVICE Comp | H2 Verdict | H2 Effect (CI) | H3 |",
            "| :---: | :--- | :---: | :--- | :--- | :---: | :--- | :---: |",
        ]
    )

    for row in summary["per_seed_breakdown"]:
        h1_str = f"{row['h1_effect_pp']:+.2f} pp [{row['h1_ci_lower_pp']:+.2f}, {row['h1_ci_upper_pp']:+.2f}]"
        h2_str = f"{row['h2_effect_pp']:+.2f} pp [{row['h2_ci_lower_pp']:+.2f}, {row['h2_ci_upper_pp']:+.2f}]"
        lines.append(
            f"| {row['seed']} | `{row['time_comparator']}` | {row['h1_verdict']} | {h1_str} | "
            f"`{row['service_comparator']}` | {row['h2_verdict']} | {h2_str} | {row['h3_verdict']} |"
        )

    lines.append("")
    return "\n".join(lines)


def run_study(
    seeds: list[int] | None = None,
    n_services: int = 200,
    n_steps: int = 4032,
    target_violation: float = 0.01,
    results_dir: Path | None = None,
    write_markdown: bool = True,
    n_estimators_override: int | None = None,
) -> dict[str, Any]:
    """Execute multi-seed study, compute aggregates, and write summary artifacts."""
    if seeds is None:
        seeds = list(range(1, 11))

    out_dir = results_dir or (REPO_ROOT / "results")
    out_dir.mkdir(parents=True, exist_ok=True)

    seed_results: list[dict[str, Any]] = []

    for seed in seeds:
        seed_path = out_dir / f"study_seed_{seed}.json"
        if seed_path.exists():
            with open(seed_path, encoding="utf-8") as f:
                res = json.load(f)
            # Recompute if old v1 format lacks per_service_sum_a
            if "per_service_sum_a" in res["time_split"]["methods"]["GBR_q95"]:
                sys.stdout.write(
                    f"[Seed {seed:2d}/{len(seeds)}] Skipping (already completed in v2 format).\n"
                )
                sys.stdout.flush()
                seed_results.append(res)
                continue

        sys.stdout.write(
            f"[Seed {seed:2d}/{len(seeds)}] Starting simulation "
            f"(services={n_services}, steps={n_steps})...\n"
        )
        sys.stdout.flush()
        t0 = time.time()

        res = run_experiment(
            seed=seed,
            n_services=n_services,
            n_steps=n_steps,
            target_violation=target_violation,
            timeout_seconds=7200.0,
            n_estimators_override=n_estimators_override,
        )
        elapsed = time.time() - t0
        sys.stdout.write(f"[Seed {seed:2d}/{len(seeds)}] Finished in {elapsed:.1f}s.\n")
        sys.stdout.flush()

        with open(seed_path, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2)

        seed_results.append(res)

    # -------------------------------------------------------------
    # Aggregation & Headline Metrics
    # -------------------------------------------------------------
    total_seeds = len(seeds)

    # 1. Hypothesis 1 (TIME split)
    h1_supported = sum(
        1
        for r in seed_results
        if "SUPPORTED" in r["time_split"]["h1"]["verdict"]
        and "NOT_SUPPORTED" not in r["time_split"]["h1"]["verdict"]
    )
    h1_effects = [r["time_split"]["h1"]["estimate"] * 100.0 for r in seed_results]
    h1_lowers = [r["time_split"]["h1"]["ci_lower"] * 100.0 for r in seed_results]
    h1_uppers = [r["time_split"]["h1"]["ci_upper"] * 100.0 for r in seed_results]

    # Pooled bootstrap across all seeds for TIME split using pooled per-service sums
    pooled_a_time = []
    pooled_b_time = []
    pooled_static_time = []
    for r in seed_results:
        comp_name = r["time_split"]["comparator"]
        gbr_m = r["time_split"]["methods"]["GBR_q95"]
        comp_m = r["time_split"]["methods"][comp_name]
        pooled_a_time.extend(gbr_m["per_service_sum_a"])
        pooled_b_time.extend(comp_m["per_service_sum_a"])
        pooled_static_time.extend(gbr_m["per_service_sum_static"])

    pooled_boot_time = paired_bootstrap_test(
        pooled_a_time, pooled_b_time, pooled_static_time, seed=42
    )

    h1_headline = {
        "verdict": "SUPPORTED"
        if h1_supported == total_seeds
        else "MIXED/NOT_SUPPORTED",
        "support_count": h1_supported,
        "total_seeds": total_seeds,
        "median_effect_pp": float(np.median(h1_effects)),
        "median_ci_lower_pp": float(np.median(h1_lowers)),
        "median_ci_upper_pp": float(np.median(h1_uppers)),
        "pooled_effect_pp": float(pooled_boot_time.estimate * 100.0),
        "pooled_ci_lower_pp": float(pooled_boot_time.ci_lower * 100.0),
        "pooled_ci_upper_pp": float(pooled_boot_time.ci_upper * 100.0),
        "pooled_p_value": float(pooled_boot_time.p_value),
    }

    # 2. Hypothesis 2 (SERVICE split)
    h2_supported = sum(
        1
        for r in seed_results
        if "SUPPORTED" in r["service_split"]["h2"]["verdict"]
        and "NOT_SUPPORTED" not in r["service_split"]["h2"]["verdict"]
    )
    h2_effects = [r["service_split"]["h2"]["estimate"] * 100.0 for r in seed_results]
    h2_lowers = [r["service_split"]["h2"]["ci_lower"] * 100.0 for r in seed_results]
    h2_uppers = [r["service_split"]["h2"]["ci_upper"] * 100.0 for r in seed_results]

    pooled_a_srv = []
    pooled_b_srv = []
    pooled_static_srv = []
    for r in seed_results:
        comp_name = r["service_split"]["comparator"]
        gbr_m = r["service_split"]["methods"]["GBR_q95"]
        comp_m = r["service_split"]["methods"][comp_name]
        pooled_a_srv.extend(gbr_m["per_service_sum_a"])
        pooled_b_srv.extend(comp_m["per_service_sum_a"])
        pooled_static_srv.extend(gbr_m["per_service_sum_static"])

    pooled_boot_srv = paired_bootstrap_test(
        pooled_a_srv, pooled_b_srv, pooled_static_srv, seed=42
    )

    h2_headline = {
        "verdict": "SUPPORTED"
        if h2_supported == total_seeds
        else "MIXED/NOT_SUPPORTED",
        "support_count": h2_supported,
        "total_seeds": total_seeds,
        "median_effect_pp": float(np.median(h2_effects)),
        "median_ci_lower_pp": float(np.median(h2_lowers)),
        "median_ci_upper_pp": float(np.median(h2_uppers)),
        "pooled_effect_pp": float(pooled_boot_srv.estimate * 100.0),
        "pooled_ci_lower_pp": float(pooled_boot_srv.ci_lower * 100.0),
        "pooled_ci_upper_pp": float(pooled_boot_srv.ci_upper * 100.0),
        "pooled_p_value": float(pooled_boot_srv.p_value),
    }

    # 3. Hypothesis 3 (Operational Feasibility)
    h3_supported = sum(1 for r in seed_results if r["h3"]["verdict"] == "SUPPORTED")
    max_v_time = max(r["h3"]["test_violation_time"] for r in seed_results)
    max_v_srv = max(r["h3"]["test_violation_service"] for r in seed_results)

    h3_headline = {
        "verdict": "SUPPORTED" if h3_supported == total_seeds else "NOT_SUPPORTED",
        "support_count": h3_supported,
        "total_seeds": total_seeds,
        "max_test_violation_time": float(max_v_time),
        "max_test_violation_service": float(max_v_srv),
        "threshold": 0.015,
    }

    # 4. Method summary statistics across seeds
    all_methods = list(seed_results[0]["time_split"]["methods"].keys())

    def _aggregate_methods(split_key: str) -> list[dict[str, Any]]:
        agg_list = []
        for m_name in all_methods:
            saves = [
                r[split_key]["methods"][m_name]["savings"] * 100.0 for r in seed_results
            ]
            viols = [
                r[split_key]["methods"][m_name]["violation_rate"] * 100.0
                for r in seed_results
            ]
            utils = [
                r[split_key]["methods"][m_name]["utilization"] * 100.0
                for r in seed_results
            ]
            wastes = [
                r[split_key]["methods"][m_name]["wastage"] * 100.0 for r in seed_results
            ]
            feasible = sum(
                1
                for r in seed_results
                if r[split_key]["methods"][m_name]["is_feasible"]
            )
            cat = (
                "ML Model"
                if m_name in ["LR", "DT", "RF", "GB", "GBR_q95"]
                else "Baseline"
            )
            agg_list.append(
                {
                    "name": m_name,
                    "category": cat,
                    "savings_pct": float(np.mean(saves)),
                    "violation_pct": float(np.mean(viols)),
                    "utilization_pct": float(np.mean(utils)),
                    "wastage_pct": float(np.mean(wastes)),
                    "feasible_count": feasible,
                }
            )
        # Sort by category and savings descending
        agg_list.sort(key=lambda x: (x["category"] == "Baseline", -x["savings_pct"]))
        return agg_list

    methods_summary_time = _aggregate_methods("time_split")
    methods_summary_service = _aggregate_methods("service_split")

    # 5. Per-seed breakdown
    per_seed_breakdown = []
    for r in seed_results:
        seed_id = r["parameters"]["seed"]
        h1_dict = r["time_split"]["h1"]
        h2_dict = r["service_split"]["h2"]
        h3_dict = r["h3"]
        per_seed_breakdown.append(
            {
                "seed": seed_id,
                "time_comparator": r["time_split"]["comparator"],
                "h1_verdict": h1_dict["verdict"],
                "h1_effect_pp": h1_dict["estimate"] * 100.0,
                "h1_ci_lower_pp": h1_dict["ci_lower"] * 100.0,
                "h1_ci_upper_pp": h1_dict["ci_upper"] * 100.0,
                "service_comparator": r["service_split"]["comparator"],
                "h2_verdict": h2_dict["verdict"],
                "h2_effect_pp": h2_dict["estimate"] * 100.0,
                "h2_ci_lower_pp": h2_dict["ci_lower"] * 100.0,
                "h2_ci_upper_pp": h2_dict["ci_upper"] * 100.0,
                "h3_verdict": h3_dict["verdict"],
            }
        )

    summary: dict[str, Any] = {
        "disclaimer": "Simulated data. Results describe the simulator, not real clouds.",
        "config": {
            "seeds": seeds,
            "n_services": n_services,
            "n_steps": n_steps,
            "target_violation": target_violation,
        },
        "headline": {
            "h1": h1_headline,
            "h2": h2_headline,
            "h3": h3_headline,
        },
        "methods_summary_time": methods_summary_time,
        "methods_summary_service": methods_summary_service,
        "per_seed_breakdown": per_seed_breakdown,
    }

    # Write summary json
    summary_path = out_dir / "study_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # Write markdown docs/results.md
    if write_markdown:
        md_content = generate_results_markdown(summary)
        docs_results_path = REPO_ROOT / "docs" / "results.md"
        with open(docs_results_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        sys.stdout.write(f"Updated {docs_results_path}.\n")
        sys.stdout.flush()

    return summary


if __name__ == "__main__":
    t_start = time.time()
    run_study()
    sys.stdout.write(f"\nAll seeds completed in {time.time() - t_start:.1f}s.\n")
