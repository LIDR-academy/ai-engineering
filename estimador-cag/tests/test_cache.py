from app.services.cache import RedisEstimationCache


def test_cache_key_changes_with_tier_model_prompt_and_transcription():
    key_a = RedisEstimationCache.make_key(
        tier="flash",
        model="deepseek-v4-flash",
        system_prompt="system v1",
        transcription="build a landing page",
    )
    key_b = RedisEstimationCache.make_key(
        tier="pro",
        model="deepseek-v4-flash",
        system_prompt="system v1",
        transcription="build a landing page",
    )
    key_c = RedisEstimationCache.make_key(
        tier="flash",
        model="deepseek-v4-pro",
        system_prompt="system v1",
        transcription="build a landing page",
    )
    key_d = RedisEstimationCache.make_key(
        tier="flash",
        model="deepseek-v4-flash",
        system_prompt="system v2",
        transcription="build a landing page",
    )
    key_e = RedisEstimationCache.make_key(
        tier="flash",
        model="deepseek-v4-flash",
        system_prompt="system v1",
        transcription="build a CRM",
    )

    assert key_a.startswith("estimation:")
    assert len({key_a, key_b, key_c, key_d, key_e}) == 5


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.ttls = {}

    def get(self, key):
        return self.values.get(key)

    def setex(self, key, ttl_seconds, value):
        self.values[key] = value
        self.ttls[key] = ttl_seconds

    def ping(self):
        return True


def test_redis_cache_miss_returns_none():
    redis = FakeRedis()
    cache = RedisEstimationCache(redis_client=redis, ttl_seconds=86400)

    assert cache.get("estimation:missing") is None


def test_redis_cache_set_then_get_roundtrip_and_ttl():
    redis = FakeRedis()
    cache = RedisEstimationCache(redis_client=redis, ttl_seconds=123)

    key = "estimation:test"
    payload = {
        "estimation": "## Estimate",
        "model": "deepseek-v4-flash",
        "tier": "flash",
        "cached": False,
    }

    cache.set(key, payload)

    assert redis.ttls[key] == 123
    assert cache.get(key) == payload


def test_redis_cache_exposes_backend_name_and_ping():
    redis = FakeRedis()
    cache = RedisEstimationCache(redis_client=redis)

    assert cache.backend_name == "redis"
    assert cache.ping() is True
