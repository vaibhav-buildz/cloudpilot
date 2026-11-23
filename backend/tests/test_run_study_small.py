"""Tests for the multi-seed study runner on small synthetic workloads."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.run_study import generate_results_markdown, run_study  # noqa: E402


def test_run_study_small_generates_valid_artifacts(tmp_path: Path):
    """Run study on 2 small seeds and verify files and schema exist deterministically."""
    summary = run_study(
        seeds=[1, 2],
        n_services=20,
        n_steps=1200,
        target_violation=0.01,
        results_dir=tmp_path,
        write_markdown=False,
        n_estimators_override=5,
    )

    # 1. Assert required output files exist
    assert (tmp_path / "study_seed_1.json").exists()
    assert (tmp_path / "study_seed_2.json").exists()
    assert (tmp_path / "study_summary.json").exists()

    # 2. Check structure of summary dictionary
    assert (
        summary["disclaimer"] == "Simulated data. Results describe the simulator, not real clouds."
    )
    assert "headline" in summary
    assert "h1" in summary["headline"]
    assert "h2" in summary["headline"]
    assert "h3" in summary["headline"]
    assert len(summary["per_seed_breakdown"]) == 2

    # 3. Verify Markdown generation does not fail
    md = generate_results_markdown(summary)
    assert "Simulated data. Results describe the simulator, not real clouds." in md
    assert "H1 (TIME Split, Superiority)" in md
    assert "H2 (SERVICE Split, Non-Inferiority)" in md
    assert "H3 (Operational Feasibility)" in md

    # 4. Verify seed file content
    with open(tmp_path / "study_seed_1.json", encoding="utf-8") as f:
        seed_1_data = json.load(f)
    assert seed_1_data["parameters"]["seed"] == 1
    assert "time_split" in seed_1_data
    assert "service_split" in seed_1_data
