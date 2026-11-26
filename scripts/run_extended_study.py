"""Run the extended-v1 protocol locally without using the web API."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.engine.extended import parse_extended_csv, run_extended  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--full", action="store_true", help="Run the ten-seed offline study.")
    source.add_argument("--csv", type=Path, help="Run one aligned CPU and memory workload.")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    seeds = list(range(1, 11)) if args.full else [42]
    data = parse_extended_csv(args.csv.read_bytes()) if args.csv else None
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for seed in seeds:
        path = args.output_dir / f"extended_v1_seed_{seed}.json"
        if path.exists():
            parser.error(f"Output already exists: {path}")
        result = run_extended(
            seed=seed,
            n_services=200 if args.full else 4,
            n_steps=4032 if args.full else 600,
            timeout_seconds=7200 if args.full else 120,
            workload=data,
            diagnostics=not args.full,
        )
        with path.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, allow_nan=False, separators=(",", ":"))
        print(f"Seed {seed}: {result['execution_time_seconds']} s, {path.stat().st_size} bytes")


if __name__ == "__main__":
    main()
