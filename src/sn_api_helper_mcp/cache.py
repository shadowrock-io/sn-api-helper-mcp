"""Simple in-memory TTL cache for API responses."""

from __future__ import annotations

import time
from typing import Any


class TTLCache:
    """Thread-safe TTL cache backed by a plain dict.

    Expired entries are evicted lazily on access — no background threads.
    """

    def __init__(self, ttl_seconds: float = 900.0, max_size: int = 256) -> None:
        self._ttl = ttl_seconds
        self._max_size = max_size
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.monotonic() > expires_at:
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        if len(self._store) >= self._max_size:
            self._evict_expired()
        if len(self._store) >= self._max_size:
            oldest_key = next(iter(self._store))
            self._store.pop(oldest_key, None)
        self._store[key] = (time.monotonic() + self._ttl, value)

    def _evict_expired(self) -> None:
        now = time.monotonic()
        expired = [k for k, (exp, _) in self._store.items() if now > exp]
        for k in expired:
            self._store.pop(k, None)
