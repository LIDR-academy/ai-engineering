import pytest

from app.services.litellm_provider import LiteLLMProvider


def test_litellm_provider_resolves_deepseek_flash_and_pro_models():
    provider = LiteLLMProvider()

    flash = provider.resolve_model("flash")
    pro = provider.resolve_model("pro")

    assert flash.tier == "flash"
    assert flash.provider == "deepseek"
    assert flash.model == "deepseek-v4-flash"
    assert flash.temperature == 0.3
    assert flash.base_url == "https://api.deepseek.com/v1"
    assert flash.api_key

    assert pro.tier == "pro"
    assert pro.provider == "deepseek"
    assert pro.model == "deepseek-v4-pro"
    assert pro.temperature == 0.3
    assert pro.base_url == "https://api.deepseek.com/v1"
    assert pro.api_key


def test_litellm_provider_resolves_kimi_with_safe_temperature():
    provider = LiteLLMProvider()

    backup = provider.resolve_model("backup")
    backup_pro = provider.resolve_model("backup_pro")

    assert backup.tier == "backup"
    assert backup.provider == "kimi"
    assert backup.model == "moonshot/kimi-k2.5"
    assert backup.temperature == 1.0
    assert backup.base_url == "https://api.moonshot.ai/v1"
    assert backup.api_key

    assert backup_pro.tier == "backup_pro"
    assert backup_pro.provider == "kimi"
    assert backup_pro.model == "moonshot/kimi-k2.6"
    assert backup_pro.temperature == 1.0
    assert backup_pro.base_url == "https://api.moonshot.ai/v1"
    assert backup_pro.api_key


def test_litellm_provider_rejects_unknown_tier():
    provider = LiteLLMProvider()

    with pytest.raises(ValueError, match="Unknown tier"):
        provider.resolve_model("unknown")


def test_litellm_provider_complete_calls_litellm_completion(monkeypatch):
    provider = LiteLLMProvider()
    calls = {}

    class FakeMessage:
        content = "## Estimate from LiteLLM"

    class FakeChoice:
        message = FakeMessage()
        finish_reason = "stop"

    class FakeUsage:
        prompt_tokens = 12
        completion_tokens = 34

    class FakeResponse:
        choices = [FakeChoice()]
        usage = FakeUsage()

    def fake_completion(**kwargs):
        calls.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr("app.services.litellm_provider.litellm.completion", fake_completion)

    result = provider.complete(
        transcription="Build a landing page",
        system_prompt="You are an estimator",
        tier="flash",
        max_tokens=2000,
    )

    assert calls["model"] == "deepseek-v4-flash"
    assert calls["api_key"]
    assert calls["api_base"] == "https://api.deepseek.com/v1"
    assert calls["temperature"] == 0.3
    assert calls["max_tokens"] == 2000
    assert calls["messages"] == [
        {"role": "system", "content": "You are an estimator"},
        {"role": "user", "content": "TRANSCRIPCION DE REUNION:\nBuild a landing page"},
    ]

    assert result["estimation"] == "## Estimate from LiteLLM"
    assert result["model"] == "deepseek-v4-flash"
    assert result["tier"] == "flash"
    assert result["provider"] == "deepseek"
    assert result["input_tokens"] == 12
    assert result["output_tokens"] == 34
    assert result["finish_reason"] == "stop"


def test_litellm_provider_complete_rejects_empty_visible_content(monkeypatch):
    provider = LiteLLMProvider()

    class FakeMessage:
        content = "   "

    class FakeChoice:
        message = FakeMessage()
        finish_reason = "stop"

    class FakeUsage:
        prompt_tokens = 12
        completion_tokens = 34

    class FakeResponse:
        choices = [FakeChoice()]
        usage = FakeUsage()

    def fake_completion(**kwargs):
        return FakeResponse()

    monkeypatch.setattr("app.services.litellm_provider.litellm.completion", fake_completion)

    with pytest.raises(RuntimeError, match="Empty response content"):
        provider.complete(
            transcription="Build a landing page",
            system_prompt="You are an estimator",
            tier="flash",
            max_tokens=2000,
        )


def test_litellm_provider_complete_with_fallback_uses_starting_tier_on_success(monkeypatch):
    provider = LiteLLMProvider()
    calls = []

    def fake_complete(*, transcription, system_prompt, tier, max_tokens=2000):
        calls.append(tier)
        return {
            "estimation": "estimate from first tier",
            "model": "deepseek-v4-flash",
            "tier": tier,
            "provider": "deepseek",
            "input_tokens": 10,
            "output_tokens": 20,
            "finish_reason": "stop",
            "timestamp": "2026-05-10T00:00:00+00:00",
        }

    monkeypatch.setattr(provider, "complete", fake_complete)

    result = provider.complete_with_fallback(
        transcription="Build a landing page",
        system_prompt="You are an estimator",
        starting_tier="flash",
        tier_ladder=["flash", "pro", "backup", "backup_pro"],
        max_tokens=2000,
    )

    assert calls == ["flash"]
    assert result["tier"] == "flash"
    assert result["fallback_used"] is False


def test_litellm_provider_complete_with_fallback_escalates_after_failure(monkeypatch):
    provider = LiteLLMProvider()
    calls = []

    def fake_complete(*, transcription, system_prompt, tier, max_tokens=2000):
        calls.append(tier)
        if tier == "flash":
            raise RuntimeError("flash failed")
        return {
            "estimation": "estimate from fallback tier",
            "model": "deepseek-v4-pro",
            "tier": tier,
            "provider": "deepseek",
            "input_tokens": 10,
            "output_tokens": 20,
            "finish_reason": "stop",
            "timestamp": "2026-05-10T00:00:00+00:00",
        }

    monkeypatch.setattr(provider, "complete", fake_complete)

    result = provider.complete_with_fallback(
        transcription="Build a landing page",
        system_prompt="You are an estimator",
        starting_tier="flash",
        tier_ladder=["flash", "pro", "backup", "backup_pro"],
        max_tokens=2000,
    )

    assert calls == ["flash", "pro"]
    assert result["tier"] == "pro"
    assert result["fallback_used"] is True


def test_litellm_provider_complete_with_fallback_raises_after_all_tiers_fail(monkeypatch):
    provider = LiteLLMProvider()

    def fake_complete(*, transcription, system_prompt, tier, max_tokens=2000):
        raise RuntimeError(f"{tier} failed")

    monkeypatch.setattr(provider, "complete", fake_complete)

    with pytest.raises(RuntimeError, match="All LLM tiers failed"):
        provider.complete_with_fallback(
            transcription="Build a landing page",
            system_prompt="You are an estimator",
            starting_tier="flash",
            tier_ladder=["flash", "pro"],
            max_tokens=2000,
        )


def test_litellm_provider_stream_yields_visible_chunks(monkeypatch):
    provider = LiteLLMProvider()
    calls = {}

    class FakeDelta:
        def __init__(self, content):
            self.content = content

    class FakeChoice:
        def __init__(self, content):
            self.delta = FakeDelta(content)

    class FakeChunk:
        def __init__(self, content):
            self.choices = [FakeChoice(content)]

    def fake_completion(**kwargs):
        calls.update(kwargs)
        return [
            FakeChunk("Hello "),
            FakeChunk(None),
            FakeChunk("world"),
        ]

    monkeypatch.setattr("app.services.litellm_provider.litellm.completion", fake_completion)

    chunks = list(
        provider.stream(
            transcription="Build a landing page",
            system_prompt="You are an estimator",
            tier="flash",
            max_tokens=2000,
        )
    )

    assert chunks == ["Hello ", "world"]
    assert calls["stream"] is True
    assert calls["model"] == "deepseek-v4-flash"
    assert calls["api_base"] == "https://api.deepseek.com/v1"
    assert calls["temperature"] == 0.3


def test_litellm_provider_stream_falls_back_to_sync_completion_when_stream_is_empty(monkeypatch):
    provider = LiteLLMProvider()
    calls = {"sync": 0}

    class FakeDelta:
        content = None

    class FakeChoice:
        delta = FakeDelta()

    class FakeChunk:
        choices = [FakeChoice()]

    def fake_completion(**kwargs):
        if kwargs.get("stream") is True:
            return [FakeChunk()]

        calls["sync"] += 1

        class FakeMessage:
            content = "sync fallback estimate"

        class FakeSyncChoice:
            message = FakeMessage()
            finish_reason = "stop"

        class FakeUsage:
            prompt_tokens = 10
            completion_tokens = 20

        class FakeResponse:
            choices = [FakeSyncChoice()]
            usage = FakeUsage()

        return FakeResponse()

    monkeypatch.setattr("app.services.litellm_provider.litellm.completion", fake_completion)

    chunks = list(
        provider.stream(
            transcription="Build a landing page",
            system_prompt="You are an estimator",
            tier="flash",
            max_tokens=2000,
        )
    )

    assert chunks == ["sync fallback estimate"]
    assert calls["sync"] == 1


def test_litellm_provider_stream_ignores_reasoning_content_and_falls_back_to_sync(monkeypatch):
    provider = LiteLLMProvider()

    class FakeDelta:
        content = None
        reasoning_content = "I am thinking about the task and should not show this."

    class FakeChoice:
        delta = FakeDelta()

    class FakeChunk:
        choices = [FakeChoice()]

    def fake_completion(**kwargs):
        if kwargs.get("stream") is True:
            return [FakeChunk()]

        class FakeMessage:
            content = "## Estimación: Clean final answer"

        class FakeSyncChoice:
            message = FakeMessage()
            finish_reason = "stop"

        class FakeUsage:
            prompt_tokens = 10
            completion_tokens = 20

        class FakeResponse:
            choices = [FakeSyncChoice()]
            usage = FakeUsage()

        return FakeResponse()

    monkeypatch.setattr("app.services.litellm_provider.litellm.completion", fake_completion)

    chunks = list(
        provider.stream(
            transcription="Build an inventory platform",
            system_prompt="You are an estimator",
            tier="flash",
            max_tokens=2000,
        )
    )

    assert chunks == ["## Estimación: Clean final answer"]
    assert "thinking" not in "".join(chunks)


def test_litellm_provider_complete_strips_process_preamble_before_estimate_heading(monkeypatch):
    provider = LiteLLMProvider()

    class FakeMessage:
        content = (
            "El usuario solicita una estimación detallada. "
            "Debo seguir las reglas. "
            "## Estimación: Plataforma de Gestión de Inventario\n\n"
            "### Desglose de tareas\n"
            "1. Backend API: 60 horas"
        )

    class FakeChoice:
        message = FakeMessage()
        finish_reason = "stop"

    class FakeUsage:
        prompt_tokens = 10
        completion_tokens = 20

    class FakeResponse:
        choices = [FakeChoice()]
        usage = FakeUsage()

    def fake_completion(**kwargs):
        return FakeResponse()

    monkeypatch.setattr("app.services.litellm_provider.litellm.completion", fake_completion)

    result = provider.complete(
        transcription="Build an inventory platform",
        system_prompt="You are an estimator",
        tier="flash",
        max_tokens=2000,
    )

    assert result["estimation"].startswith("## Estimación:")
    assert "El usuario solicita" not in result["estimation"]


def test_litellm_provider_uses_litellm_provider_prefix_for_kimi_models():
    provider = LiteLLMProvider()

    backup = provider.resolve_model("backup")
    backup_pro = provider.resolve_model("backup_pro")

    assert backup.model.startswith("moonshot/")
    assert backup.model == "moonshot/kimi-k2.5"

    assert backup_pro.model.startswith("moonshot/")
    assert backup_pro.model == "moonshot/kimi-k2.6"


def test_litellm_provider_complete_includes_cost_metadata(monkeypatch):
    provider = LiteLLMProvider()

    class FakeMessage:
        content = "## Estimate with cost"

    class FakeChoice:
        message = FakeMessage()
        finish_reason = "stop"

    class FakeUsage:
        prompt_tokens = 1000
        completion_tokens = 2000

    class FakeResponse:
        choices = [FakeChoice()]
        usage = FakeUsage()

    def fake_completion(**kwargs):
        return FakeResponse()

    monkeypatch.setattr("app.services.litellm_provider.litellm.completion", fake_completion)

    result = provider.complete(
        transcription="Build a landing page",
        system_prompt="You are an estimator",
        tier="flash",
        max_tokens=2000,
    )

    assert result["cost_usd"] is not None
    assert result["cost_usd"] > 0
    assert result["cost_source"] == "static_estimate"
    assert result["pricing_model"] == "deepseek-v4-flash"
