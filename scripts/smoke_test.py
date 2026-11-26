"""End-to-end production smoke test for CloudPilot (Render + Vercel + Supabase)."""

from __future__ import annotations

import os
import sys

import httpx


def _require_env(name: str) -> str:
    val = os.environ.get(name, "").strip()
    if not val:
        print(f"FAIL config: {name} environment variable is not set")
        sys.exit(1)
    return val


def main() -> int:
    backend_url = _require_env("BACKEND_URL").rstrip("/")
    frontend_url = _require_env("FRONTEND_URL").rstrip("/")
    api_key = _require_env("CLOUDPILOT_API_KEY")
    allowed_origin = os.environ.get("ALLOWED_ORIGIN", frontend_url).strip().rstrip("/")

    failures = 0

    def report(name: str, ok: bool, detail: str = "") -> None:
        nonlocal failures
        if ok:
            print(f"PASS {name}" + (f" ({detail})" if detail else ""))
        else:
            failures += 1
            print(f"FAIL {name}" + (f": {detail}" if detail else ""))

    with httpx.Client(timeout=90.0) as client:
        # (a) GET /health 200
        try:
            r = client.get(f"{backend_url}/health")
            report("health", r.status_code == 200, f"HTTP {r.status_code}")
        except Exception as exc:
            report("health", False, type(exc).__name__)

        # (b) GET /ready 200
        try:
            r = client.get(f"{backend_url}/ready")
            report("ready", r.status_code == 200, f"HTTP {r.status_code}")
        except Exception as exc:
            report("ready", False, type(exc).__name__)

        # (c) Unauthenticated request to protected endpoint is rejected (401/403)
        try:
            r = client.get(f"{backend_url}/api/limits")
            report(
                "auth_required", r.status_code in (401, 403), f"HTTP {r.status_code}"
            )
        except Exception as exc:
            report("auth_required", False, type(exc).__name__)

        # (d) Small simulation via Vercel proxy succeeds and appears in Supabase read-back
        try:
            sim_res = client.post(
                f"{frontend_url}/api/simulate",
                headers={"Origin": frontend_url, "Content-Type": "application/json"},
                json={
                    "n_services": 4,
                    "n_steps": 120,
                    "seed": 42,
                    "target_violation": 0.01,
                },
            )
            if sim_res.status_code != 200:
                report(
                    "proxy_simulate_and_readback",
                    False,
                    f"POST HTTP {sim_res.status_code}",
                )
            else:
                body = sim_res.json()
                run_id = body.get("run_id")
                saved = body.get("saved")
                if not saved or not run_id:
                    report(
                        "proxy_simulate_and_readback",
                        False,
                        f"saved={saved}, run_id_present={bool(run_id)}",
                    )
                else:
                    read_res = client.get(
                        f"{frontend_url}/api/runs/{run_id}",
                        cookies=sim_res.cookies,
                    )
                    read_ok = (
                        read_res.status_code == 200
                        and read_res.json().get("id") == run_id
                    )
                    report(
                        "proxy_simulate_and_readback",
                        read_ok,
                        f"POST 200, GET HTTP {read_res.status_code}",
                    )
                    # Best-effort cleanup of smoke-test row
                    client.delete(
                        f"{frontend_url}/api/runs/{run_id}",
                        headers={"Origin": frontend_url},
                        cookies=sim_res.cookies,
                    )
        except Exception as exc:
            report("proxy_simulate_and_readback", False, type(exc).__name__)

        # (e) CORS preflight: ALLOWED_ORIGIN allowed, https://evil.example rejected
        try:
            good = client.options(
                f"{backend_url}/api/limits",
                headers={
                    "Origin": allowed_origin,
                    "Access-Control-Request-Method": "GET",
                },
            )
            evil = client.options(
                f"{backend_url}/api/limits",
                headers={
                    "Origin": "https://evil.example",
                    "Access-Control-Request-Method": "GET",
                },
            )
            good_acao = good.headers.get("access-control-allow-origin", "")
            evil_acao = evil.headers.get("access-control-allow-origin", "")
            cors_ok = (
                good.status_code == 200
                and good_acao == allowed_origin
                and evil_acao != "https://evil.example"
            )
            report(
                "cors_preflight",
                cors_ok,
                f"allowed HTTP {good.status_code}, evil HTTP {evil.status_code}",
            )
        except Exception as exc:
            report("cors_preflight", False, type(exc).__name__)

        # (f) Simulation caps reject oversized request
        try:
            limits_res = client.get(
                f"{backend_url}/api/limits",
                headers={"X-API-Key": api_key},
            )
            max_services = 20
            if limits_res.status_code == 200:
                max_services = int(limits_res.json().get("max_services", 20))

            over_res = client.post(
                f"{backend_url}/api/simulate",
                headers={"X-API-Key": api_key, "Content-Type": "application/json"},
                json={
                    "n_services": max_services + 100,
                    "n_steps": 120,
                    "seed": 42,
                    "target_violation": 0.01,
                },
            )
            report(
                "simulation_caps",
                over_res.status_code == 422,
                f"HTTP {over_res.status_code}",
            )
        except Exception as exc:
            report("simulation_caps", False, type(exc).__name__)

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
