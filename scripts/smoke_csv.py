"""Verify production CSV evaluation, metrics persistence, and visitor scoping."""

import os
from pathlib import Path

import httpx


def main() -> None:
    origin = os.environ["FRONTEND_URL"].rstrip("/")
    sample = Path(__file__).resolve().parents[1] / "frontend/public/sample-workload.csv"
    with httpx.Client(base_url=origin, timeout=90.0) as client:

        def upload(content: bytes) -> httpx.Response:
            return client.post(
                "/api/simulate/csv",
                headers={"Origin": origin},
                files={"file": ("sample.csv", content, "text/csv")},
                data={"target_violation": "0.01"},
            )

        response = upload(sample.read_bytes())
        response.raise_for_status()
        result = response.json()
        run_id = result.get("run_id")
        assert run_id and result["saved"], "CSV experiment was not saved"
        try:
            assert result["parameters"]["n_services"] == 4
            assert result["parameters"]["n_steps"] == 600
            assert sum(result["workload_analysis"]["histogram"]["counts"]) == 2400
            for split in ("time_split", "service_split"):
                assert result[split]["methods"]["GBR_q95"]["mse"] >= 0
                assert result[split]["traces"]
            saved = client.get(f"/api/runs/{run_id}")
            saved.raise_for_status()
            row = saved.json()
            assert row["source"] == "csv" and row["status"] == "ok"
            assert row["result"]["workload_analysis"] == result["workload_analysis"]
            assert row["result"]["time_split"] == result["time_split"]
            with httpx.Client(base_url=origin, timeout=30.0) as other:
                assert other.get(f"/api/runs/{run_id}").status_code == 404
            invalid = upload(b"service_id,timestamp\na,0000\n")
            assert invalid.status_code == 422 and "cpu_demand" in invalid.json()["detail"]
        finally:
            client.delete(f"/api/runs/{run_id}", headers={"Origin": origin}).raise_for_status()
    print("PASS CSV evaluation, diagnostics readback, visitor isolation, invalid file and cleanup")


if __name__ == "__main__":
    main()
