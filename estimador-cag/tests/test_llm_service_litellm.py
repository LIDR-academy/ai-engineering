from app.services import llm_service


class FakeCache:
    backend_name = "redis"

    def __init__(self):
        self.stored = {}

    def make_key(self, *, tier, model, system_prompt, transcription):
        return f"estimation:{tier}:{model}"

    def get(self, key):
        return None

    def set(self, key, value):
        self.stored[key] = value


class FakeLiteLLMProvider:
    def __init__(self):
        self.calls = []

    def resolve_model(self, tier):
        class Resolved:
            model = "deepseek-v4-flash"

        return Resolved()

    def complete_with_fallback(
        self,
        *,
        transcription,
        system_prompt,
        starting_tier,
        tier_ladder,
        max_tokens=2000,
        history=None,
        max_history_turns=6,
    ):
        self.calls.append(
            {
                "transcription": transcription,
                "system_prompt": system_prompt,
                "starting_tier": starting_tier,
                "tier_ladder": tier_ladder,
                "max_tokens": max_tokens,
                "history": history,
                "max_history_turns": max_history_turns,
            }
        )
        return {
            "estimation": "estimate from litellm",
            "model": "deepseek-v4-flash",
            "tier": starting_tier,
            "provider": "deepseek",
            "input_tokens": 10,
            "output_tokens": 20,
            "finish_reason": "stop",
            "fallback_used": False,
            "timestamp": "2026-05-10T00:00:00+00:00",
        }


def test_estimate_uses_litellm_provider_with_redis_cache(monkeypatch):
    fake_cache = FakeCache()
    fake_provider = FakeLiteLLMProvider()

    monkeypatch.setattr(llm_service, "build_redis_cache", lambda: fake_cache)
    monkeypatch.setattr(llm_service, "LiteLLMProvider", lambda: fake_provider)

    result = llm_service.estimate(
        transcription="Build a landing page",
        tier="flash",
    )

    assert result["estimation"] == "estimate from litellm"
    assert result["cached"] is False
    assert result["cache_backend"] == "redis"
    assert result["fallback_used"] is False

    assert fake_provider.calls
    assert fake_provider.calls[0]["starting_tier"] == "flash"
    assert fake_provider.calls[0]["tier_ladder"] == ["flash", "pro", "backup", "backup_pro"]

    assert fake_cache.stored


def test_llm_service_no_longer_exposes_old_get_model_config_path():
    assert not hasattr(llm_service, "get_model_config")
