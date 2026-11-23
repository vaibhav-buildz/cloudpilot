"""Static analysis test verifying absence of future-leakage interpolation terms."""

from __future__ import annotations

import re
from pathlib import Path

FORBIDDEN_PATTERNS = [
    re.compile(r"\bbfill\b", re.IGNORECASE),
    re.compile(r"\bbackfill\b", re.IGNORECASE),
]


def test_no_bfill_or_backfill_in_backend_app():
    """Ensure forbidden backward-fill operations never appear in backend/app."""
    app_dir = Path(__file__).resolve().parent.parent / "app"
    assert app_dir.exists(), f"App directory not found: {app_dir}"

    violations = []
    py_files = list(app_dir.rglob("*.py"))
    assert len(py_files) > 0, "No python files found in backend/app"

    for py_file in py_files:
        content = py_file.read_text(encoding="utf-8")
        for line_num, line in enumerate(content.splitlines(), start=1):
            for pattern in FORBIDDEN_PATTERNS:
                if pattern.search(line):
                    violations.append(
                        f"{py_file.name}:{line_num}: {line.strip()} (matches {pattern.pattern})"
                    )

    assert not violations, (
        "Forbidden backward filling detected in backend/app codebase:\n" + "\n".join(violations)
    )
