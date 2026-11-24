"""Sync study summary JSON to the frontend source bundle."""

from __future__ import annotations

import pathlib
import shutil

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "results" / "study_summary.json"
DEST_DIR = ROOT / "frontend" / "src" / "data"
DEST = DEST_DIR / "study_summary.json"


def sync_study_data() -> None:
    if not SRC.exists():
        raise FileNotFoundError(f"Source file not found: {SRC}")
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy(SRC, DEST)
    print(f"Copied {SRC} -> {DEST} ({DEST.stat().st_size} bytes)")


if __name__ == "__main__":
    sync_study_data()
