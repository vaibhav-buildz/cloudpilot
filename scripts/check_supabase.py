"""Supabase connection and CRUD verification script."""

from __future__ import annotations

import asyncio
import json
import pathlib
import re
import sys
from typing import Any

import httpx

# Ensure backend directory is in sys.path
ROOT = pathlib.Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.repository import SupabaseRunRepository  # noqa: E402


def load_supabase_credentials(env_path: pathlib.Path) -> tuple[str, str]:
    if not env_path.exists():
        print("FAIL config - .env file not found")
        sys.exit(1)

    url = ""
    key = ""
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith("SUPABASE_URL="):
                val = stripped.split("=", 1)[1].strip()
                if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
                    val = val[1:-1]
                url = val
            elif stripped.startswith("SUPABASE_SERVICE_KEY="):
                val = stripped.split("=", 1)[1].strip()
                if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
                    val = val[1:-1]
                key = val

    if not url or not key:
        print("FAIL config - SUPABASE_URL or SUPABASE_SERVICE_KEY missing from .env")
        sys.exit(1)

    return url, key


def mask_secrets(value: str, service_key: str) -> str:
    masked = value
    if service_key:
        masked = masked.replace(service_key, "[REDACTED]")
    masked = re.sub(r"sb_secret_[A-Za-z0-9_\-]+", "[REDACTED]", masked)
    masked = re.sub(
        r"eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+",
        "[REDACTED]",
        masked,
    )
    return masked


def print_fail(
    step: str,
    status_code: int | None,
    custom_hint: str | None = None,
    error_fields: dict[str, Any] | None = None,
    service_key: str = "",
) -> None:
    hint_map = {
        401: "wrong key or header format",
        403: "permissions",
        404: "migration not run or wrong URL",
    }
    hint = hint_map.get(status_code) if status_code else None
    if not hint and custom_hint:
        hint = custom_hint
    elif not hint:
        hint = "request failed"

    if status_code is not None:
        print(f"FAIL {step} HTTP {status_code} ({hint})")
    else:
        print(f"FAIL {step} ({hint})")

    if error_fields:
        for field in ("code", "message", "details", "hint"):
            val = error_fields.get(field)
            if val is not None:
                print(f"  {field}: {mask_secrets(str(val), service_key)}")

    sys.exit(1)


def extract_status_code(exc: Exception) -> int | None:
    msg = str(exc)
    match = re.search(r"HTTP\s+(\d+)", msg)
    if match:
        return int(match.group(1))
    return None


async def main() -> None:
    url, key = load_supabase_credentials(ROOT / ".env")
    repo = SupabaseRunRepository(
        supabase_url=url,
        supabase_service_key=key,
    )

    last_error_fields: dict[str, Any] | None = None

    async def capture_error_hook(response: httpx.Response) -> None:
        nonlocal last_error_fields
        if response.status_code >= 400:
            try:
                await response.aread()
                parsed = json.loads(response.content.decode("utf-8"))
                if isinstance(parsed, dict):
                    last_error_fields = {
                        k: parsed.get(k)
                        for k in ("code", "message", "details", "hint")
                        if k in parsed
                    }
            except Exception:
                last_error_fields = None

    repo._client.event_hooks["response"].append(capture_error_hook)

    try:
        # 1) ping()
        last_error_fields = None
        is_healthy = await repo.ping()
        if not is_healthy:
            try:
                resp = await repo._client.get("/simulation_runs", params={"limit": "1"})
                status = resp.status_code
            except Exception as e:
                status = extract_status_code(e)
            print_fail("ping", status, error_fields=last_error_fields, service_key=key)
        print("ping: OK")

        # 2) save_run
        last_error_fields = None
        try:
            record = await repo.save_run(
                client_id="check-script",
                source="simulated",
                params={"check": True},
                status="ok",
                result={"check": True},
            )
            run_id = record.get("id") if isinstance(record, dict) else None
            if not run_id:
                print_fail("insert", None, "no ID returned in record")
            print("insert: OK")
        except Exception as exc:
            status = extract_status_code(exc)
            print_fail(
                "insert",
                status,
                type(exc).__name__,
                error_fields=last_error_fields,
                service_key=key,
            )

        # 3) get_run and list_runs
        last_error_fields = None
        try:
            fetched = await repo.get_run("check-script", run_id)
            if not fetched or fetched.get("id") != run_id:
                print_fail("read", None, "get_run failed to retrieve inserted row")

            runs = await repo.list_runs("check-script", limit=10)
            if not any(r.get("id") == run_id for r in runs):
                print_fail("read", None, "list_runs missing inserted row")

            print("read: OK")
        except Exception as exc:
            status = extract_status_code(exc)
            print_fail(
                "read",
                status,
                type(exc).__name__,
                error_fields=last_error_fields,
                service_key=key,
            )

        # 4) delete_run and 5) confirm row is gone
        last_error_fields = None
        try:
            deleted = await repo.delete_run("check-script", run_id)
            if not deleted:
                print_fail("delete", None, "delete_run returned False")

            confirmed_gone = await repo.get_run("check-script", run_id)
            if confirmed_gone is not None:
                print_fail("delete", None, "row still exists after delete")

            print("delete: OK")
        except Exception as exc:
            status = extract_status_code(exc)
            print_fail(
                "delete",
                status,
                type(exc).__name__,
                error_fields=last_error_fields,
                service_key=key,
            )

    finally:
        await repo.aclose()


if __name__ == "__main__":
    asyncio.run(main())
