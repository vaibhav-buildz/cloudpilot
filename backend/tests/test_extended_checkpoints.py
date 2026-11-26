"""Verify the offline study can resume from a complete, matching seed record."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.run_extended_study import FULL_CONFIG, read_checkpoint, write_checkpoint  # noqa: E402


def test_full_study_checkpoint_cannot_be_overwritten_and_rejects_tampering(tmp_path):
    path = tmp_path / "extended_v1_seed_1.json"
    result = {
        "mode": "extended-v1",
        "parameters": {**FULL_CONFIG, "seed": 1},
        "execution_time_seconds": 12.3,
    }
    provenance = {"test": "expected configuration"}
    write_checkpoint(path, result, provenance)
    assert read_checkpoint(path, 1, provenance) == result
    with pytest.raises(FileExistsError):
        write_checkpoint(path, result, provenance)
    with pytest.raises(ValueError, match="metadata or checksum"):
        read_checkpoint(path, 2, provenance)
    record = json.loads(path.read_bytes())
    record["execution_time_seconds"] = 1
    path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ValueError, match="metadata or checksum"):
        read_checkpoint(path, 1, provenance)
