"""
LAYER: services (caching)
RESPONSIBILITY: Exact match cache primitives for LLM estimations.
WHY IT EXISTS: Keeps repeated identical estimations from calling the LLM again,
               reducing latency and cost while preserving CAG simplicity.
DEPENDS_ON: hashlib, json, time, redis when RedisEstimationCache is used

ARCHITECTURE NOTE:
Redis here is a response cache. It is not retrieval, not RAG, and not semantic
search. The CAG knowledge still comes from static examples injected into the
prompt by llm_service.py.
"""

import hashlib
import json
import time
from collections.abc import Callable
from functools import wraps
from typing import Any

_cache_store: dict[str, tuple[float, dict[str, Any]]] = {}


class RedisEstimationCache:
    """
    Redis backed exact response cache for estimations.

    LAYER: services
    RESPONSIBILITY: Build deterministic cache keys and store serialized
                    estimation responses in Redis with TTL.
    WHY IT EXISTS: Provides a real process independent cache backend for
                   canonical Session 03 compliance.
    DEPENDS_ON: A Redis client compatible with get, setex, and ping.
    """

    key_prefix = "estimation"

    def __init__(self, redis_client: Any, ttl_seconds: int = 86400) -> None:
        self.redis_client = redis_client
        self.ttl_seconds = ttl_seconds

    @property
    def backend_name(self) -> str:
        """Expose backend name for logs and /metrics."""
        return "redis"

    @staticmethod
    def make_key(
        *,
        tier: str,
        model: str,
        system_prompt: str,
        transcription: str,
    ) -> str:
        """
        Build a deterministic exact match cache key.

        The key changes when tier, model, system prompt, or transcription changes.
        The stored value may then be safely reused only for truly equivalent
        estimation requests.
        """
        payload = {
            "tier": tier,
            "model": model,
            "system_prompt_sha256": hashlib.sha256(
                system_prompt.encode("utf-8")
            ).hexdigest(),
            "transcription_sha256": hashlib.sha256(
                transcription.encode("utf-8")
            ).hexdigest(),
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return f"{RedisEstimationCache.key_prefix}:{digest}"

    def get(self, key: str) -> dict[str, Any] | None:
        """Return cached estimation payload or None on miss."""
        raw = self.redis_client.get(key)
        if raw is None:
            return None

        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")

        value = json.loads(raw)
        if not isinstance(value, dict):
            raise TypeError("Cached estimation payload must decode to a dict.")
        return value

    def set(self, key: str, value: dict[str, Any]) -> None:
        """Store estimation payload with configured TTL."""
        payload = json.dumps(value, ensure_ascii=False, sort_keys=True)
        self.redis_client.setex(key, self.ttl_seconds, payload)

    def ping(self) -> bool:
        """Return True when Redis is reachable."""
        return bool(self.redis_client.ping())


def _make_key(transcription: str, tier: str) -> str:
    """Create deterministic SHA256 key from transcription and tier."""
    raw = f"{tier}::{transcription}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def cached_estimate(ttl_seconds: int = 300):
    """
    Decorator for estimate(transcription, tier).

    LAYER: services
    RESPONSIBILITY: Wrap the estimation function with in memory exact cache.
    WHY IT EXISTS: Keeps the existing stable milestone working while the Redis
                   backend is introduced incrementally with TDD.
    DEPENDS_ON: _make_key, _cache_store
    """

    def decorator(func: Callable[..., dict[str, Any]]):
        @wraps(func)
        def wrapper(transcription: str, tier: str | None = None):
            effective_tier = tier or "flash"
            key = _make_key(transcription, effective_tier)
            now = time.time()

            if key in _cache_store:
                cached_at, cached_result = _cache_store[key]
                if now - cached_at < ttl_seconds:
                    result = cached_result.copy()
                    result["cached"] = True
                    return result

                del _cache_store[key]

            result = func(transcription, tier).copy()
            result["cached"] = False
            _cache_store[key] = (now, result.copy())
            return result

        return wrapper

    return decorator
