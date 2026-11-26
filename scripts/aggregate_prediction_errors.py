"""Aggregate prediction errors from the ten original per-seed study results."""

import argparse
import hashlib
import json
from pathlib import Path
from statistics import mean


def aggregate(source: Path) -> dict:
    config = {"n_services": 200, "n_steps": 4032, "target_violation": 0.01}
    seeds = list(range(1, 11))
    files, runs = {}, []
    for seed in seeds:
        name = f"study_seed_{seed}.json"
        raw = (source / name).read_bytes()
        files[name] = hashlib.sha256(raw).hexdigest()
        run = json.loads(raw)
        if run["parameters"] != {**config, "seed": seed}:
            raise ValueError(f"Unexpected experiment parameters in {name}")
        runs.append(run)

    metrics = {}
    for split in ("time_split", "service_split"):
        metrics[split] = {}
        for method in runs[0][split]["methods"]:
            if method == "static":
                continue
            rows = [run[split]["methods"][method] for run in runs]
            metrics[split][method] = {
                "mae": mean(row["mae"] for row in rows),
                "mse": mean(row["mse"] if "mse" in row else row["rmse"] ** 2 for row in rows),
                "rmse": mean(row["rmse"] for row in rows),
            }
    return {
        "config": {**config, "seeds": seeds},
        "provenance": {
            "source": "Original v2 per-seed study results",
            "sha256": files,
            "aggregation": (
                "Unweighted mean of each seed's held-out metric, for each split and method. "
                "Legacy per-seed MSE is recovered from full-precision RMSE squared "
                "(within floating-point roundoff). Mean RMSE is computed separately."
            ),
        },
        "metrics": metrics,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(aggregate(args.source), indent=2) + "\n", encoding="utf-8")
