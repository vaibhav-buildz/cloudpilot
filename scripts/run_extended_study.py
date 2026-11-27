"""Run the extended-v1 protocol locally without using the web API."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
import tempfile
from contextlib import nullcontext
from importlib.metadata import version
from pathlib import Path

from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.engine.extended import parse_extended_csv, run_extended  # noqa: E402

FULL_CONFIG = {"n_services": 200, "n_steps": 4032, "target_violation": 0.01}


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def study_provenance(rf_jobs: int = -1, native_threads: int | None = None) -> dict:
    engine = ROOT / "backend/app/engine"
    sources = sorted(engine.glob("*.py")) + [
        ROOT / "backend/app/workload_limits.py",
        Path(__file__).resolve(),
    ]
    return {
        "protocol": "extended-v1",
        "seeds": list(range(1, 11)),
        "configuration": FULL_CONFIG,
        "default_estimators": True,
        "diagnostics": False,
        "timeout_seconds_per_seed": 7200,
        "python": platform.python_version(),
        "dependencies": {
            name: version(name)
            for name in ("numpy", "scipy", "scikit-learn", "threadpoolctl")
        },
        "execution_profile": {"rf_jobs": rf_jobs, "native_threads": native_threads},
        "sources": {
            p.relative_to(ROOT).as_posix(): hashlib.sha256(
                p.read_bytes().replace(b"\r\n", b"\n")
            ).hexdigest()
            for p in sources
        },
    }


def write_checkpoint(path: Path, result: dict, provenance: dict) -> None:
    record = {
        **result,
        "study_provenance": provenance,
        "result_sha256": hashlib.sha256(canonical_json(result)).hexdigest(),
    }
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(canonical_json(record))
            stream.flush()
            os.fsync(stream.fileno())
            stream.close()
            # Publish a complete checkpoint atomically without replacing another run's file.
            os.link(temporary, path)
        finally:
            stream.close()
            temporary.unlink()


def read_checkpoint(path: Path, seed: int, provenance: dict) -> dict:
    record = json.loads(path.read_bytes())
    if not isinstance(record, dict):
        raise ValueError(f"Invalid checkpoint record: {path}")
    recorded_provenance = record.pop("study_provenance", None)
    digest = record.pop("result_sha256", None)
    if (
        recorded_provenance != provenance
        or record.get("mode") != "extended-v1"
        or record.get("parameters") != {**FULL_CONFIG, "seed": seed}
        or digest != hashlib.sha256(canonical_json(record)).hexdigest()
    ):
        raise ValueError(f"Checkpoint metadata or checksum mismatch: {path}")
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--full", action="store_true", help="Run the ten-seed offline study."
    )
    source.add_argument(
        "--csv", type=Path, help="Run one aligned CPU and memory workload."
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--resume", action="store_true", help="Reuse verified full-study seeds."
    )
    parser.add_argument(
        "--seed", type=int, choices=range(1, 11), help="Run one full-study seed."
    )
    parser.add_argument(
        "--rf-jobs", type=int, default=-1, help="Random Forest job count."
    )
    parser.add_argument(
        "--native-threads", type=int, help="Limit BLAS and OpenMP thread pools."
    )
    args = parser.parse_args()
    if args.resume and not args.full:
        parser.error("--resume requires --full")
    if args.seed is not None and not args.full:
        parser.error("--seed requires --full")
    if args.rf_jobs < -1 or args.rf_jobs == 0:
        parser.error("--rf-jobs must be -1 or positive")
    if args.native_threads is not None and args.native_threads < 1:
        parser.error("--native-threads must be positive")
    seeds = (
        [args.seed]
        if args.seed is not None
        else (list(range(1, 11)) if args.full else [42])
    )
    data = parse_extended_csv(args.csv.read_bytes()) if args.csv else None
    args.output_dir.mkdir(parents=True, exist_ok=True)
    provenance = (
        study_provenance(args.rf_jobs, args.native_threads) if args.full else None
    )
    for seed in seeds:
        path = args.output_dir / f"extended_v1_seed_{seed}.json"
        if path.exists():
            if not args.resume:
                parser.error(f"Output already exists: {path}")
            try:
                previous = read_checkpoint(path, seed, provenance)
            except (ValueError, KeyError, TypeError) as exc:
                parser.error(str(exc))
            print(
                f"Seed {seed}: reused verified checkpoint ({previous['execution_time_seconds']} s)"
            )
            continue
        print(f"Seed {seed}: running", flush=True)
        limits = (
            threadpool_limits(args.native_threads)
            if args.native_threads
            else nullcontext()
        )
        with limits:
            result = run_extended(
                seed=seed,
                n_services=200 if args.full else 4,
                n_steps=4032 if args.full else 600,
                timeout_seconds=7200 if args.full else 120,
                workload=data,
                diagnostics=not args.full,
                rf_jobs=args.rf_jobs,
            )
        if provenance is None:
            with path.open("x", encoding="utf-8") as stream:
                json.dump(result, stream, allow_nan=False, separators=(",", ":"))
        else:
            write_checkpoint(path, result, provenance)
        print(
            f"Seed {seed}: {result['execution_time_seconds']} s, {path.stat().st_size} bytes"
        )


if __name__ == "__main__":
    main()
