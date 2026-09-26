from capucine.cache import TTLCache


def test_get_or_set_returns_cached_value_within_ttl():
    cache = TTLCache(ttl_seconds=60)
    calls = []

    def compute():
        calls.append(1)
        return "value"

    assert cache.get_or_set("k", compute) == "value"
    assert cache.get_or_set("k", compute) == "value"
    assert len(calls) == 1


def test_get_or_set_recomputes_after_ttl_expires():
    cache = TTLCache(ttl_seconds=0)
    calls = []

    def compute():
        calls.append(1)
        return "value"

    cache.get_or_set("k", compute)
    cache.get_or_set("k", compute)
    assert len(calls) == 2


def test_invalidate_only_clears_matching_prefix():
    cache = TTLCache(ttl_seconds=60)
    cache.get_or_set("tasks:50", lambda: "a")
    cache.get_or_set("events:30:50", lambda: "b")

    cache.invalidate("tasks:")

    calls = []
    cache.get_or_set("tasks:50", lambda: calls.append(1) or "a2")
    cache.get_or_set("events:30:50", lambda: calls.append(1) or "b2")

    assert calls == [1]
