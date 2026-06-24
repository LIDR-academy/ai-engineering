from app.services import llm_service
from app.services.conversation import ConversationTurn


class FakeCache:
    backend_name = "memory_test"

    def make_key(self, *, tier, model, system_prompt, transcription):
        return "conversation-cache-key"

    def get(self, key):
        return None

    def set(self, key, value):
        pass


class FakeProvider:
    def __init__(self):
        self.complete_calls = []
        self.stream_calls = []

    def resolve_model(self, tier):
        class Resolved:
            model = "deepseek-v4-flash"
            provider = "deepseek"

        return Resolved()

    def complete_with_fallback(self, **kwargs):
        self.complete_calls.append(kwargs)
        return {
            "estimation": "## Estimate with history",
            "model": "deepseek-v4-flash",
            "tier": kwargs.get("tier", kwargs.get("starting_tier")),
            "provider": "deepseek",
            "input_tokens": 10,
            "output_tokens": 20,
            "cost_usd": 0.0001,
            "cost_source": "static_estimate",
            "pricing_model": "deepseek-v4-flash",
            "finish_reason": "stop",
            "timestamp": "2026-05-10T00:00:00+00:00",
        }

    def stream(self, **kwargs):
        self.stream_calls.append(kwargs)
        yield "hello"


def test_estimate_passes_conversation_history_to_provider(monkeypatch):
    fake_provider = FakeProvider()

    monkeypatch.setattr(llm_service, "build_redis_cache", lambda: FakeCache())
    monkeypatch.setattr(llm_service, "LiteLLMProvider", lambda: fake_provider)

    history = [
        ConversationTurn(role="user", content="Previous scope"),
        ConversationTurn(role="assistant", content="Previous estimate"),
    ]

    result = llm_service.estimate(
        transcription="Now estimate this",
        tier="flash",
        history=history,
        max_history_turns=2,
    )

    assert result["estimation"] == "## Estimate with history"
    assert fake_provider.complete_calls[0]["history"] == history
    assert fake_provider.complete_calls[0]["max_history_turns"] == 2


def test_estimate_stream_passes_conversation_history_to_provider(monkeypatch):
    fake_provider = FakeProvider()
    monkeypatch.setattr(llm_service, "LiteLLMProvider", lambda: fake_provider)

    history = [
        ConversationTurn(role="user", content="Previous scope"),
        ConversationTurn(role="assistant", content="Previous estimate"),
    ]

    chunks = list(
        llm_service.estimate_stream(
            transcription="Now estimate this",
            tier="flash",
            history=history,
            max_history_turns=2,
        )
    )

    assert chunks == ["hello"]
    assert fake_provider.stream_calls[0]["history"] == history
    assert fake_provider.stream_calls[0]["max_history_turns"] == 2
