"""Database repository layer for simulation runs persistence and querying."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

import httpx

from app.config import Settings

logger = logging.getLogger("cloudpilot")
RUN_SUMMARY = "id,created_at,client_id,source,params,status,error,duration_ms"
SAVE_ATTEMPT_TIMEOUT = httpx.Timeout(1.25)


@runtime_checkable
class RunRepository(Protocol):
    """Protocol defining persistence operations for simulation runs."""

    async def save_run(
        self,
        client_id: str,
        source: str,
        params: dict[str, Any],
        status: str,
        result: dict[str, Any] | None = None,
        error: str | None = None,
        duration_ms: int | None = None,
    ) -> dict[str, Any]:
        """Save a simulation run record and return the created record."""
        ...

    async def list_runs(
        self,
        client_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List simulation runs for a client ordered by created_at desc."""
        ...

    async def get_run(
        self,
        client_id: str,
        run_id: str,
    ) -> dict[str, Any] | None:
        """Fetch a specific run by ID scoped to client_id."""
        ...

    async def delete_run(
        self,
        client_id: str,
        run_id: str,
    ) -> bool:
        """Delete a run by ID scoped to client_id. Returns True if deleted."""
        ...

    async def prune(
        self,
        client_id: str,
        keep: int = 50,
    ) -> int:
        """Prune runs for a client, keeping the latest `keep` runs. Returns count deleted."""
        ...

    async def ping(self) -> bool:
        """Check repository health / connectivity. Returns True if healthy."""
        ...


class InMemoryRunRepository:
    """Thread-safe in-memory simulation runs store for development and testing."""

    def __init__(self) -> None:
        self._runs: dict[str, dict[str, Any]] = {}
        self.is_healthy: bool = True

    async def save_run(
        self,
        client_id: str,
        source: str,
        params: dict[str, Any],
        status: str,
        result: dict[str, Any] | None = None,
        error: str | None = None,
        duration_ms: int | None = None,
    ) -> dict[str, Any]:
        run_id = str(uuid.uuid4())
        created_at = datetime.now(UTC).isoformat()
        record = {
            "id": run_id,
            "created_at": created_at,
            "client_id": client_id,
            "source": source,
            "params": params,
            "status": status,
            "result": result,
            "error": error,
            "duration_ms": duration_ms,
        }
        self._runs[run_id] = record
        return record

    async def list_runs(
        self,
        client_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        client_runs = [r for r in self._runs.values() if r["client_id"] == client_id]
        client_runs.sort(key=lambda r: r["created_at"], reverse=True)
        return [{**run, "result": None} for run in client_runs[offset : offset + limit]]

    async def get_run(
        self,
        client_id: str,
        run_id: str,
    ) -> dict[str, Any] | None:
        run = self._runs.get(run_id)
        if run and run["client_id"] == client_id:
            return run
        return None

    async def delete_run(
        self,
        client_id: str,
        run_id: str,
    ) -> bool:
        run = self._runs.get(run_id)
        if run and run["client_id"] == client_id:
            del self._runs[run_id]
            return True
        return False

    async def prune(
        self,
        client_id: str,
        keep: int = 50,
    ) -> int:
        client_runs = [r for r in self._runs.values() if r["client_id"] == client_id]
        client_runs.sort(key=lambda r: r["created_at"], reverse=True)
        to_delete = client_runs[keep:]
        for r in to_delete:
            del self._runs[r["id"]]
        return len(to_delete)

    async def ping(self) -> bool:
        return self.is_healthy


class SupabaseRunRepository:
    """PostgREST-backed persistence repository targeting Supabase Postgres."""

    def __init__(
        self,
        supabase_url: str,
        supabase_service_key: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        base_url = f"{supabase_url.rstrip('/')}/rest/v1"
        headers = {
            "apikey": supabase_service_key,
            "Authorization": f"Bearer {supabase_service_key}",
            "Content-Type": "application/json",
        }
        if client is not None:
            self._client = client
        else:
            self._client = httpx.AsyncClient(
                base_url=base_url,
                headers=headers,
                timeout=httpx.Timeout(5.0),
            )
        self._owned_client = client is None

    async def aclose(self) -> None:
        """Close underlying client connection pool."""
        if self._owned_client:
            await self._client.aclose()

    async def _request_with_retry(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Execute HTTP request with 1 retry on 5xx errors or network exceptions."""
        for attempt in range(2):
            try:
                resp = await self._client.request(method, path, **kwargs)
                if resp.status_code < 500 or attempt == 1:
                    return resp
            except httpx.RequestError as exc:
                if attempt == 0:
                    continue
                logger.warning(
                    "PostgREST operation failed after retry",
                    extra={"method": method, "path": path, "error": type(exc).__name__},
                )
                raise RuntimeError(f"PostgREST operation failed: {type(exc).__name__}") from None

        raise RuntimeError("PostgREST request failed with server error")

    @staticmethod
    def _format_postgrest_error(action: str, resp: httpx.Response) -> str:
        """Build a concise error message including PostgREST code and message."""
        base = f"Failed to {action}: HTTP {resp.status_code}"
        try:
            data = resp.json()
            if isinstance(data, dict):
                parts = []
                if data.get("code"):
                    parts.append(str(data["code"]))
                if data.get("message"):
                    parts.append(str(data["message"]))
                if parts:
                    return f"{base} ({': '.join(parts)})"
        except Exception:
            pass
        return base

    async def save_run(
        self,
        client_id: str,
        source: str,
        params: dict[str, Any],
        status: str,
        result: dict[str, Any] | None = None,
        error: str | None = None,
        duration_ms: int | None = None,
    ) -> dict[str, Any]:
        run_id = str(uuid.uuid4())
        payload = {
            "id": run_id,
            "client_id": client_id,
            "source": source,
            "params": params,
            "status": status,
            "result": result,
            "error": error,
            "duration_ms": duration_ms,
        }
        headers = {"Prefer": "resolution=ignore-duplicates,return=representation"}
        write_params = {"on_conflict": "id", "select": RUN_SUMMARY}
        try:
            resp = await self._request_with_retry(
                "POST",
                "/simulation_runs",
                json=payload,
                headers=headers,
                params=write_params,
                timeout=SAVE_ATTEMPT_TIMEOUT,
            )
        except RuntimeError:
            # The last attempt may have committed before its connection failed.
            resp = None
        if resp is not None:
            if resp.status_code in (200, 201):
                rows = resp.json()
                if isinstance(rows, list) and rows and rows[0].get("id") == run_id:
                    return rows[0]
            elif resp.status_code < 500:
                raise RuntimeError(self._format_postgrest_error("save simulation run", resp))

        # A replay of an already committed insert returns no rows with ignore-duplicates.
        verification = await self._client.get(
            "/simulation_runs",
            params={"client_id": f"eq.{client_id}", "id": f"eq.{run_id}", "select": RUN_SUMMARY},
            timeout=SAVE_ATTEMPT_TIMEOUT,
        )
        if verification.status_code == 200:
            rows = verification.json()
            if isinstance(rows, list) and rows and rows[0].get("id") == run_id:
                return rows[0]
        raise RuntimeError("Simulation save could not be confirmed")

    async def list_runs(
        self,
        client_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        query_params = {
            "client_id": f"eq.{client_id}",
            "select": RUN_SUMMARY,
            "order": "created_at.desc",
            "limit": str(limit),
            "offset": str(offset),
        }
        resp = await self._request_with_retry(
            "GET",
            "/simulation_runs",
            params=query_params,
        )
        if resp.status_code != 200:
            raise RuntimeError(self._format_postgrest_error("list simulation runs", resp))
        data = resp.json()
        return [{**row, "result": None} for row in data] if isinstance(data, list) else []

    async def get_run(
        self,
        client_id: str,
        run_id: str,
    ) -> dict[str, Any] | None:
        query_params = {
            "client_id": f"eq.{client_id}",
            "id": f"eq.{run_id}",
        }
        resp = await self._request_with_retry(
            "GET",
            "/simulation_runs",
            params=query_params,
        )
        if resp.status_code != 200:
            raise RuntimeError(self._format_postgrest_error("get simulation run", resp))
        data = resp.json()
        if isinstance(data, list) and len(data) > 0:
            return data[0]
        return None

    async def delete_run(
        self,
        client_id: str,
        run_id: str,
    ) -> bool:
        query_params = {
            "client_id": f"eq.{client_id}",
            "id": f"eq.{run_id}",
            "select": "id",
        }
        headers = {"Prefer": "return=representation"}
        resp = await self._request_with_retry(
            "DELETE",
            "/simulation_runs",
            params=query_params,
            headers=headers,
        )
        if resp.status_code != 200:
            raise RuntimeError(self._format_postgrest_error("delete simulation run", resp))
        data = resp.json()
        return isinstance(data, list) and len(data) > 0

    async def prune(
        self,
        client_id: str,
        keep: int = 50,
    ) -> int:
        query_params = {
            "client_id": f"eq.{client_id}",
            "select": "id",
            "order": "created_at.desc",
            "offset": str(keep),
        }
        resp = await self._request_with_retry(
            "GET",
            "/simulation_runs",
            params=query_params,
        )
        if resp.status_code != 200:
            raise RuntimeError(self._format_postgrest_error("find runs to prune", resp))
        items = resp.json()
        if not isinstance(items, list) or len(items) == 0:
            return 0

        ids = [item["id"] for item in items if "id" in item]
        if not ids:
            return 0

        delete_params = {
            "client_id": f"eq.{client_id}",
            "id": f"in.({','.join(ids)})",
            "select": "id",
        }
        headers = {"Prefer": "return=representation"}
        del_resp = await self._request_with_retry(
            "DELETE",
            "/simulation_runs",
            params=delete_params,
            headers=headers,
        )
        if del_resp.status_code == 200:
            deleted_items = del_resp.json()
            return len(deleted_items) if isinstance(deleted_items, list) else 0
        raise RuntimeError(self._format_postgrest_error("prune simulation runs", del_resp))

    async def ping(self) -> bool:
        try:
            resp = await self._client.get(
                "/simulation_runs",
                params={"limit": "1", "select": "id"},
                timeout=httpx.Timeout(2.0),
            )
            return resp.status_code < 400
        except Exception:
            return False


def get_repository(settings: Settings) -> RunRepository:
    """Factory creating appropriate RunRepository based on application configuration."""
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_KEY:
        return SupabaseRunRepository(
            supabase_url=settings.SUPABASE_URL,
            supabase_service_key=settings.SUPABASE_SERVICE_KEY,
        )
    logger.warning(
        "Supabase credentials not configured; using InMemoryRunRepository fallback",
        extra={"app_env": settings.APP_ENV},
    )
    return InMemoryRunRepository()
