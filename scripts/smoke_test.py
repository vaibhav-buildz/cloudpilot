"""End-to-end production smoke test for CloudPilot (Render + Vercel + Supabase)."""

from __future__ import annotations

import json
import os
import re
import sys
import uuid

import httpx

_CREDENTIAL_FIELD = re.compile(
    r"(?i)([\"']?[\w-]*(?:key|token|secret|password|authorization|cookie)[\"']?\s*[:=]\s*)"
    r'(?:"(?:\\.|[^"\\])*"|\'[^\']*\'|(?:Bearer\s+)?[^\s,;}\]]+)'
)
_CREDENTIAL_VALUE = re.compile(r"(?:sb_secret_[\w-]+|rnd_[\w-]+|eyJ[\w-]+\.[\w-]+\.[\w-]+)")


def _response_detail(response: httpx.Response, *secrets: str) -> str:
    """Return a bounded diagnostic without known credentials or multiline output."""
    body = response.text
    for secret in sorted(filter(None, secrets), key=len, reverse=True):
        body = body.replace(secret, "[REDACTED]")
        body = body.replace(json.dumps(secret, ensure_ascii=False)[1:-1], "[REDACTED]")
    body = _CREDENTIAL_FIELD.sub(r"\1[REDACTED]", body)
    body = _CREDENTIAL_VALUE.sub("[REDACTED]", body)
    body = " ".join(body.split())
    return f"HTTP {response.status_code}" + (f" body={body[:500]!r}" if body else "")


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
    direct_headers = {"X-API-Key": api_key, "X-Visitor-Id": str(uuid.uuid4())}
    secrets = (
        api_key,
        direct_headers["X-Visitor-Id"],
        os.environ.get("SUPABASE_SERVICE_KEY", ""),
    )
    workload = {"n_services": 4, "n_steps": 600, "seed": 42, "target_violation": 0.01}

    failures = 0

    def describe(response: httpx.Response, ok: bool = False) -> str:
        return f"HTTP {response.status_code}" if ok else _response_detail(response, *secrets)

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
            report("health", r.status_code == 200, describe(r, r.status_code == 200))
        except Exception as exc:
            report("health", False, type(exc).__name__)

        # (b) GET /ready 200
        try:
            r = client.get(f"{backend_url}/ready")
            report("ready", r.status_code == 200, describe(r, r.status_code == 200))
        except Exception as exc:
            report("ready", False, type(exc).__name__)

        # (c) Unauthenticated request to protected endpoint is rejected (401/403)
        try:
            r = client.get(f"{backend_url}/api/limits")
            auth_ok = r.status_code in (401, 403)
            report("auth_required", auth_ok, describe(r, auth_ok))
        except Exception as exc:
            report("auth_required", False, type(exc).__name__)

        # (d) Small simulation via Vercel proxy succeeds and appears in Supabase read-back
        try:
            sim_res = client.post(
                f"{frontend_url}/api/simulate",
                headers={"Origin": frontend_url, "Content-Type": "application/json"},
                json=workload,
            )
            if sim_res.status_code != 200:
                report(
                    "proxy_simulate_and_readback",
                    False,
                    f"POST {describe(sim_res)}",
                )
            else:
                body = sim_res.json()
                run_id = body.get("run_id")
                saved = body.get("saved")
                if saved is not True or not run_id:
                    report(
                        "proxy_simulate_and_readback",
                        False,
                        f"saved={saved is True}, run_id_present={bool(run_id)}",
                    )
                else:
                    read_res = client.get(f"{frontend_url}/api/runs/{run_id}")
                    read_ok = read_res.status_code == 200 and read_res.json().get("id") == run_id
                    report(
                        "proxy_simulate_and_readback",
                        read_ok,
                        f"POST 200, GET {describe(read_res, read_ok)}",
                    )
                    # Best-effort cleanup of smoke-test row
                    try:
                        cleanup = client.delete(
                            f"{frontend_url}/api/runs/{run_id}",
                            headers={"Origin": frontend_url},
                        )
                        if cleanup.status_code != 200:
                            print(f"WARN smoke-test cleanup: {describe(cleanup)}")
                    except httpx.RequestError as exc:
                        print(f"WARN smoke-test cleanup: {type(exc).__name__}")
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
                and evil.status_code == 400
                and evil_acao != "https://evil.example"
            )
            report(
                "cors_preflight",
                cors_ok,
                f"allowed {describe(good, cors_ok)}, evil {describe(evil, cors_ok)}",
            )
        except Exception as exc:
            report("cors_preflight", False, type(exc).__name__)

        # (f) Simulation caps reject oversized request
        try:
            limits_res = client.get(
                f"{backend_url}/api/limits",
                headers=direct_headers,
            )
            if limits_res.status_code != 200:
                report("simulation_caps", False, f"GET limits {describe(limits_res)}")
            else:
                max_services = int(limits_res.json()["max_services"])
                over_res = client.post(
                    f"{backend_url}/api/simulate",
                    headers=direct_headers,
                    json={**workload, "n_services": max_services + 100},
                )
                caps_ok = over_res.status_code == 422 and "SIM_MAX_SERVICES" in str(
                    over_res.json().get("detail")
                )
                report("simulation_caps", caps_ok, f"POST {describe(over_res, caps_ok)}")
        except Exception as exc:
            report("simulation_caps", False, type(exc).__name__)

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
