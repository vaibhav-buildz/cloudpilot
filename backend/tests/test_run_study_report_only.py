"""Test that run_study in --report-only mode preserves all numeric metrics."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.run_study import run_study  # noqa: E402


def _extract_numeric_fields(obj: Any, path: str = "") -> dict[str, float]:
    """Recursively extract all numeric fields and their dotted paths."""
    numerics: dict[str, float] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            new_path = f"{path}.{k}" if path else k
            numerics.update(_extract_numeric_fields(v, new_path))
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            new_path = f"{path}[{idx}]"
            numerics.update(_extract_numeric_fields(item, new_path))
    elif isinstance(obj, int | float) and not isinstance(obj, bool):
        numerics[path] = float(obj)
    return numerics


def test_report_only_preserves_numeric_metrics() -> None:
    """Verify --report-only regenerates reports without changing numeric values."""
    summary_path = REPO_ROOT / "results" / "study_summary.json"
    assert summary_path.exists(), "results/study_summary.json must exist"

    with open(summary_path, encoding="utf-8") as f:
        baseline_summary = json.load(f)

    baseline_numerics = _extract_numeric_fields(baseline_summary)

    # Re-run report generation
    new_summary = run_study(report_only=True, write_markdown=True)
    new_numerics = _extract_numeric_fields(new_summary)

    # Every numeric key present in baseline must match identically in the new report
    assert len(baseline_numerics) > 0
    for key, base_val in baseline_numerics.items():
        assert key in new_numerics, f"Numeric key {key} missing in regenerated summary"
        assert new_numerics[key] == pytest.approx(base_val, abs=1e-9), (
            f"Value mismatch for {key}: expected {base_val}, got {new_numerics[key]}"
        )

    # Verify headline verdicts follow the refined 3-state D6 rules
    assert new_summary["headline"]["h1"]["verdict"] == "NOT_SUPPORTED"
    assert new_summary["headline"]["h2"]["verdict"] == "NOT_SUPPORTED"
    assert new_summary["headline"]["h3"]["verdict"] == "SUPPORTED"
