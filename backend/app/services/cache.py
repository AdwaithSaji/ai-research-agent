"""Process-lifetime TTL cache for search results and fetched pages.

Avoiding repeat searches/fetches for the same query or URL within a run (and
across nearby-in-time runs) is one of the main token/latency cost-control
levers in this project — every cache hit is an LLM/network call skipped.
"""
from __future__ import annotations

import time
from typing import Generic, TypeVar

T = TypeVar("T")


class TTLCache(Generic[T]):
    def __init__(self, ttl_seconds: int = 3600, max_entries: int = 500) -> None:
        self._ttl = ttl_seconds
        self._max_entries = max_entries
        self._store: dict[str, tuple[float, T]] = {}

    def get(self, key: str) -> T | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.monotonic() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: T) -> None:
        if len(self._store) >= self._max_entries:
            oldest_key = min(self._store, key=lambda k: self._store[k][0])
            del self._store[oldest_key]
        self._store[key] = (time.monotonic() + self._ttl, value)

    def __len__(self) -> int:
        return len(self._store)


def normalize_key(*parts: str) -> str:
    return "|".join(p.strip().lower() for p in parts)
