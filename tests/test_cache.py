"""Tests for the TTL cache."""

import time

from sn_api_helper_mcp.cache import TTLCache


def test_cache_set_and_get() -> None:
    cache = TTLCache(ttl_seconds=60.0)
    cache.set("key1", "value1")
    assert cache.get("key1") == "value1"


def test_cache_miss_returns_none() -> None:
    cache = TTLCache(ttl_seconds=60.0)
    assert cache.get("nonexistent") is None


def test_cache_ttl_expiry() -> None:
    cache = TTLCache(ttl_seconds=0.1)
    cache.set("key1", "value1")
    assert cache.get("key1") == "value1"
    time.sleep(0.15)
    assert cache.get("key1") is None


def test_cache_max_size_eviction() -> None:
    cache = TTLCache(ttl_seconds=60.0, max_size=2)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)
    assert len(cache._store) <= 2
    assert cache.get("c") == 3


def test_cache_overwrite() -> None:
    cache = TTLCache(ttl_seconds=60.0)
    cache.set("key", "old")
    cache.set("key", "new")
    assert cache.get("key") == "new"
