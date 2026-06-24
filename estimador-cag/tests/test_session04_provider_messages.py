from app.services.litellm_provider import LiteLLMProvider


def test_litellm_provider_complete_messages_sends_exact_role_messages(monkeypatch):
    provider = LiteLLMProvider()
    calls = {}

    class FakeMessage:
        content = "## Estimate from message API"

    class FakeChoice:
        message = FakeMessage()
        finish_reason = "stop"

    class FakeUsage:
        prompt_tokens = 21
        completion_tokens = 34

    class FakeResponse:
        choices = [FakeChoice()]
        usage = FakeUsage()

    def fake_completion(**kwargs):
        calls.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr("app.services.litellm_provider.litellm.completion", fake_completion)

    messages = [
        {"role": "system", "content": "System prompt from template"},
        {"role": "user", "content": "User prompt from template"},
    ]

    result = provider.complete_messages(
        messages=messages,
        tier="flash",
        max_tokens=1200,
    )

    assert calls["messages"] == messages
    assert calls["model"] == "deepseek-v4-flash"
    assert calls["max_tokens"] == 1200
    assert result["estimation"] == "## Estimate from message API"
    assert result["provider"] == "deepseek"
    assert result["tier"] == "flash"


def test_litellm_provider_complete_with_fallback_messages_uses_message_api(monkeypatch):
    provider = LiteLLMProvider()
    calls = []

    def fake_complete_messages(*, messages, tier, max_tokens=2000):
        calls.append({"messages": messages, "tier": tier, "max_tokens": max_tokens})
        return {
            "estimation": "estimate from message fallback",
            "model": "deepseek-v4-flash",
            "tier": tier,
            "provider": "deepseek",
            "input_tokens": 10,
            "output_tokens": 20,
            "finish_reason": "stop",
            "timestamp": "2026-05-12T00:00:00+00:00",
        }

    monkeypatch.setattr(provider, "complete_messages", fake_complete_messages)

    messages = [
        {"role": "system", "content": "System"},
        {"role": "user", "content": "User"},
    ]

    result = provider.complete_with_fallback_messages(
        messages=messages,
        starting_tier="flash",
        tier_ladder=["flash", "pro", "backup", "backup_pro"],
        max_tokens=900,
    )

    assert calls == [{"messages": messages, "tier": "flash", "max_tokens": 900}]
    assert result["fallback_used"] is False
    assert result["estimation"] == "estimate from message fallback"
