from app.services.llm_service import estimate_with_exact_cache


class FakeExactCache:
    backend_name = "redis"

    def __init__(self, cached_value=None):
        self.cached_value = cached_value
        self.keys = []
        self.stored = {}

    def make_key(self, *, tier, model, system_prompt, transcription):
        key = f"estimation:{tier}:{model}:{hash(system_prompt)}:{hash(transcription)}"
        self.keys.append(key)
        return key

    def get(self, key):
        return self.cached_value

    def set(self, key, value):
        self.stored[key] = value


def test_estimate_with_exact_cache_returns_hit_without_calling_model():
    cache = FakeExactCache(
        cached_value={
            "estimation": "cached estimate",
            "model": "deepseek-v4-flash",
            "tier": "flash",
            "provider": "deepseek",
            "input_tokens": 10,
            "output_tokens": 20,
            "timestamp": "2026-05-10T00:00:00+00:00",
        }
    )

    def model_call():
        raise AssertionError("Model call must not happen on cache hit.")

    result = estimate_with_exact_cache(
        transcription="build a landing page",
        tier="flash",
        model="deepseek-v4-flash",
        system_prompt="system prompt",
        cache=cache,
        model_call=model_call,
    )

    assert result["estimation"] == "cached estimate"
    assert result["cached"] is True
    assert result["cache_backend"] == "redis"
    assert cache.stored == {}


def test_estimate_with_exact_cache_calls_model_and_stores_on_miss():
    cache = FakeExactCache(cached_value=None)
    calls = {"count": 0}

    def model_call():
        calls["count"] += 1
        return {
            "estimation": "fresh estimate",
            "model": "deepseek-v4-flash",
            "tier": "flash",
            "provider": "deepseek",
            "input_tokens": 11,
            "output_tokens": 22,
            "timestamp": "2026-05-10T00:00:00+00:00",
        }

    result = estimate_with_exact_cache(
        transcription="build a landing page",
        tier="flash",
        model="deepseek-v4-flash",
        system_prompt="system prompt",
        cache=cache,
        model_call=model_call,
    )

    assert calls["count"] == 1
    assert result["estimation"] == "fresh estimate"
    assert result["cached"] is False
    assert result["cache_backend"] == "redis"

    assert len(cache.stored) == 1
    stored_value = next(iter(cache.stored.values()))
    assert stored_value["estimation"] == "fresh estimate"
    assert stored_value["cached"] is False
    assert stored_value["cache_backend"] == "redis"


def test_build_redis_cache_uses_settings_url_and_ttl(monkeypatch):
    from app.services import llm_service

    created = {}

    class FakeRedisClient:
        @classmethod
        def from_url(cls, url, decode_responses):
            created["url"] = url
            created["decode_responses"] = decode_responses
            return cls()

    monkeypatch.setattr(llm_service, "Redis", FakeRedisClient)
    monkeypatch.setattr(llm_service.settings, "redis_url", "redis://example:6379/9")
    monkeypatch.setattr(llm_service.settings, "cache_ttl_seconds", 456)

    cache = llm_service.build_redis_cache()

    assert created == {
        "url": "redis://example:6379/9",
        "decode_responses": True,
    }
    assert cache.backend_name == "redis"
    assert cache.ttl_seconds == 456


def test_estimate_uses_redis_cache_hit_without_calling_provider(monkeypatch):
    from app.services import llm_service

    class FakeCache:
        backend_name = "redis"

        def make_key(self, *, tier, model, system_prompt, transcription):
            return "estimation:hit"

        def get(self, key):
            return {
                "estimation": "cached from redis",
                "model": "deepseek-v4-flash",
                "tier": "flash",
                "provider": "deepseek",
                "input_tokens": 10,
                "output_tokens": 20,
                "timestamp": "2026-05-10T00:00:00+00:00",
            }

        def set(self, key, value):
            raise AssertionError("Cache hit must not write a new value.")

    class FakeCompletions:
        def create(self, **kwargs):
            raise AssertionError("Provider must not be called on Redis cache hit.")

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    monkeypatch.setattr(llm_service, "build_redis_cache", lambda: FakeCache())

    result = llm_service.estimate(
        transcription="unique redis cache hit transcript",
        tier="flash",
    )

    assert result["estimation"] == "cached from redis"
    assert result["cached"] is True
    assert result["cache_backend"] == "redis"
