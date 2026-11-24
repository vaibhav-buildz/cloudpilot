"""Supabase connection and CRUD verification script."""

from __future__ import annotations

import asyncio
import pathlib
import re
import sys

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
            if stripped.startswith("SUPABASE_URL=") or stripped.startswith(
                "NEXT_PUBLIC_SUPABASE_URL="
            ):
                val = stripped.split("=", 1)[1].strip()
                if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
                    val = val[1:-1]
                if not url or stripped.startswith("SUPABASE_URL="):
                    url = val
            elif (
                stripped.startswith("SUPABASE_SERVICE_KEY=")
                or stripped.startswith("SUPABASE_SERVICE_ROLE_KEY=")
                or stripped.startswith("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=")
                or stripped.startswith("SUPABASE_KEY=")
            ):
                val = stripped.split("=", 1)[1].strip()
                if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
                    val = val[1:-1]
                if not key or stripped.startswith("SUPABASE_SERVICE_KEY="):
                    key = val

    if not url or not key:
        print("FAIL config - SUPABASE_URL or SUPABASE_SERVICE_KEY missing from .env")
        sys.exit(1)

    return url, key


def print_fail(
    step: str, status_code: int | None, custom_hint: str | None = None
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

    try:
        # 1) ping()
        is_healthy = await repo.ping()
        if not is_healthy:
            try:
                resp = await repo._client.get("/simulation_runs", params={"limit": "1"})
                status = resp.status_code
            except Exception as e:
                status = extract_status_code(e)
            print_fail("ping", status)
        print("ping: OK")

        # 2) save_run
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
            print_fail("insert", status, type(exc).__name__)

        # 3) get_run and list_runs
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
            print_fail("read", status, type(exc).__name__)

        # 4) delete_run and 5) confirm row is gone
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
            print_fail("delete", status, type(exc).__name__)

    finally:
        await repo.aclose()


if __name__ == "__main__":
    asyncio.run(main())
