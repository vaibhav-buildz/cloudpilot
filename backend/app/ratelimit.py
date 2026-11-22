"""In-memory sliding window rate limiter for /api endpoints."""

from __future__ import annotations

import threading
import time
from collections import defaultdict

from fastapi import Depends, HTTPException, Request, status

from app.config import Settings, get_settings
from app.security import hash_client_key


class SlidingWindowRateLimiter:
    """Thread-safe in-memory sliding window rate limiter."""

    def __init__(self, window_seconds: float = 60.0) -> None:
        self.window_seconds = window_seconds
        self._history: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def reset(self) -> None:
        """Clear all rate limit history (useful for test isolation)."""
        with self._lock:
            self._history.clear()

    def extract_client_id(self, request: Request) -> str:
        """Extract client identifier from API key hash or fallback to client IP."""
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return f"key:{hash_client_key(api_key)}"

        client_host = request.client.host if request.client else "127.0.0.1"
        return f"ip:{client_host}"

    def check(self, request: Request, settings: Settings = Depends(get_settings)) -> None:
        """Evaluate sliding window limit.

        Raises HTTP 429 with Retry-After header if limit is exceeded.
        """
        limit = settings.RATE_LIMIT_PER_MIN
        client_id = self.extract_client_id(request)
        now = time.time()
        window_start = now - self.window_seconds

        with self._lock:
            # Filter out entries outside the sliding window
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


# Global rate limiter instance
rate_limiter = SlidingWindowRateLimiter()
