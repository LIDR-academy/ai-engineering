from app.services.litellm_provider import LiteLLMProvider


def test_verify_tier_visible_output_marks_backup_pro_reliable(monkeypatch):
    provider = LiteLLMProvider()

    def fake_complete(*, transcription, system_prompt, tier, max_tokens=2000):
        assert tier == "backup_pro"
        return {
            "estimation": "## Estimación: visible Kimi output",
            "model": "kimi-k2.6",
            "tier": "backup_pro",
            "provider": "kimi",
            "input_tokens": 10,
            "output_tokens": 20,
            "finish_reason": "stop",
            "timestamp": "2026-05-10T00:00:00+00:00",
        }

    monkeypatch.setattr(provider, "complete", fake_complete)

    result = provider.verify_visible_output(
        tier="backup_pro",
        transcription="Estimate a small landing page.",
        system_prompt="You are an estimator.",
    )

    assert result["tier"] == "backup_pro"
    assert result["provider"] == "kimi"
    assert result["visible_output"] is True
    assert result["reliable"] is True
    assert result["error_type"] is None


def test_verify_tier_visible_output_marks_empty_backup_pro_unreliable(monkeypatch):
    provider = LiteLLMProvider()

    def fake_complete(*, transcription, system_prompt, tier, max_tokens=2000):
        raise RuntimeError("Empty response content from model=kimi-k2.6")

    monkeypatch.setattr(provider, "complete", fake_complete)

    result = provider.verify_visible_output(
        tier="backup_pro",
        transcription="Estimate a small landing page.",
        system_prompt="You are an estimator.",
    )

    assert result["tier"] == "backup_pro"
    assert result["provider"] == "kimi"
    assert result["visible_output"] is False
    assert result["reliable"] is False
    assert result["error_type"] == "RuntimeError"
