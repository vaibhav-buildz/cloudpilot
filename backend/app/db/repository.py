"""Database repository layer for simulation runs persistence and querying."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

import httpx

from app.config import Settings

logger = logging.getLogger("cloudpilot")


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
        return client_runs[offset : offset + limit]

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
        last_exc: Exception | None = None
        for attempt in range(2):
            try:
                resp = await self._client.request(method, path, **kwargs)
                if resp.status_code < 500:
                    return resp
                if attempt == 0:
                    continue
                return resp
            except (httpx.RequestError, httpx.TimeoutException) as exc:
                last_exc = exc
                if attempt == 0:
                    continue
                logger.warning(
                    "PostgREST operation failed after retry",
                    extra={"method": method, "path": path, "error": type(exc).__name__},
                )
                raise RuntimeError(f"PostgREST operation failed: {type(exc).__name__}") from None

        if last_exc:
            raise RuntimeError(f"PostgREST operation failed: {type(last_exc).__name__}") from None
        raise RuntimeError("PostgREST request failed with server error")

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
        payload = {
            "client_id": client_id,
            "source": source,
            "params": params,
            "status": status,
            "result": result,
            "error": error,
            "duration_ms": duration_ms,
        }
        headers = {"Prefer": "return=representation"}
        resp = await self._request_with_retry(
            "POST",
            "/simulation_runs",
            json=payload,
            headers=headers,
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"Failed to save simulation run: HTTP {resp.status_code}")
        data = resp.json()
        if isinstance(data, list) and len(data) > 0:
            return data[0]
        if isinstance(data, dict):
            return data
        raise RuntimeError("Unexpected response structure from PostgREST insert")

    async def list_runs(
        self,
        client_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        query_params = {
            "client_id": f"eq.{client_id}",
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
            raise RuntimeError(f"Failed to list simulation runs: HTTP {resp.status_code}")
        data = resp.json()
        return data if isinstance(data, list) else []

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
            raise RuntimeError(f"Failed to get simulation run: HTTP {resp.status_code}")
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
        }
        headers = {"Prefer": "return=representation"}
        resp = await self._request_with_retry(
            "DELETE",
            "/simulation_runs",
            params=query_params,
            headers=headers,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to delete simulation run: HTTP {resp.status_code}")
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
            return 0
        items = resp.json()
        if not isinstance(items, list) or len(items) == 0:
            return 0

        ids = [item["id"] for item in items if "id" in item]
        if not ids:
            return 0

        delete_params = {
            "client_id": f"eq.{client_id}",
            "id": f"in.({','.join(ids)})",
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
        return 0

    async def ping(self) -> bool:
        try:
            resp = await self._client.get(
                "/simulation_runs",
                params={"limit": "1"},
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
