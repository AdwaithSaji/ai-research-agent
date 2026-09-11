import time

from app.services.cache import TTLCache, normalize_key


def test_cache_set_and_get():
    cache: TTLCache[str] = TTLCache(ttl_seconds=60)
    cache.set("k1", "value1")
    assert cache.get("k1") == "value1"


def test_cache_miss_returns_none():
    cache: TTLCache[str] = TTLCache(ttl_seconds=60)
    assert cache.get("missing") is None


def test_cache_expires_entries():
    cache: TTLCache[str] = TTLCache(ttl_seconds=0)
    cache.set("k1", "value1")
    time.sleep(0.01)
    assert cache.get("k1") is None


def test_cache_evicts_oldest_when_full():
    cache: TTLCache[str] = TTLCache(ttl_seconds=60, max_entries=2)
    cache.set("a", "1")
    cache.set("b", "2")
    cache.set("c", "3")
    assert len(cache) == 2


def test_normalize_key_is_case_insensitive():
    assert normalize_key("Hello", "World") == normalize_key("hello", "world")
