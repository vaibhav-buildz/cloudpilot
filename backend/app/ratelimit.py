"""In-memory sliding window rate limiters for /api endpoints."""

from __future__ import annotations

import hashlib
import threading
import time
import uuid
from collections import defaultdict

from fastapi import Depends, HTTPException, Request, status

from app.config import Settings, get_settings
from app.security import hash_client_key


class SlidingWindowRateLimiter:
    """Thread-safe in-memory sliding window rate limiter per client."""

    def __init__(self, window_seconds: float = 60.0) -> None:
        self.window_seconds = window_seconds
        self._history: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def reset(self) -> None:
        """Clear all rate limit history (useful for test isolation)."""
        with self._lock:
            self._history.clear()

    def extract_client_id(self, request: Request) -> str:
        """Extract client identifier from request state, API key hash, or fallback to IP."""
        state_client_id = getattr(request.state, "client_id", None)
        if state_client_id:
            return f"key:{state_client_id}"

        api_key = request.headers.get("X-API-Key")
        if api_key:
            visitor_id = request.headers.get("X-Visitor-Id")
            if visitor_id:
                try:
                    parsed = uuid.UUID(visitor_id, version=4)
                    if str(parsed) == visitor_id.lower() and parsed.version == 4:
                        scoped = hashlib.sha256(f"{api_key}:{visitor_id}".encode()).hexdigest()
                        return f"key:{scoped}"
                except (ValueError, AttributeError):
                    pass
            return f"key:{hash_client_key(api_key)}"

        client_host = request.client.host if request.client else "127.0.0.1"
        return f"ip:{client_host}"

    def check(self, request: Request, settings: Settings = Depends(get_settings)) -> None:
        """Evaluate sliding window limit for the requesting client.

        Raises HTTP 429 with Retry-After header if limit is exceeded.
        """
        limit = settings.RATE_LIMIT_PER_MIN
        client_id = self.extract_client_id(request)
        now = time.time()
        window_start = now - self.window_seconds

        with self._lock:
            timestamps = [ts for ts in self._history[client_id] if ts > window_start]

            if len(timestamps) >= limit:
                oldest_in_window = timestamps[0]
                retry_after = max(1, int(oldest_in_window + self.window_seconds - now))
                self._history[client_id] = timestamps
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded",
                    headers={"Retry-After": str(retry_after)},
                )

            timestamps.append(now)
            self._history[client_id] = timestamps


class GlobalSimulationRateLimiter:
    """Thread-safe in-memory global rate limiter across all clients for simulation endpoints."""

    def __init__(self, window_seconds: float = 60.0) -> None:
        self.window_seconds = window_seconds
        self._timestamps: list[float] = []
        self._lock = threading.Lock()

    def reset(self) -> None:
        """Clear global simulation rate limit history (useful for test isolation)."""
        with self._lock:
            self._timestamps.clear()

    def check(self, settings: Settings = Depends(get_settings)) -> None:
        """Enforce global simulation limit across all clients.

        Raises HTTP 429 with Retry-After header if limit is exceeded.
        """
        limit = settings.GLOBAL_SIM_PER_MIN
        now = time.time()
        window_start = now - self.window_seconds

        with self._lock:
            self._timestamps = [ts for ts in self._timestamps if ts > window_start]
            if len(self._timestamps) >= limit:
                oldest_in_window = self._timestamps[0]
                retry_after = max(1, int(oldest_in_window + self.window_seconds - now))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Global simulation rate limit exceeded. Please retry later.",
                    headers={"Retry-After": str(retry_after)},
                )
            self._timestamps.append(now)


# Global rate limiter instances
rate_limiter = SlidingWindowRateLimiter()
global_sim_limiter = GlobalSimulationRateLimiter()
