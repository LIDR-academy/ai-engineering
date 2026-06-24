from app.services.conversation import ConversationTurn
from app.services.litellm_provider import LiteLLMProvider


def test_litellm_provider_complete_accepts_conversation_history(monkeypatch):
    provider = LiteLLMProvider()
    captured = {}

    class FakeMessage:
        content = "## Estimate with history"

    class FakeChoice:
        message = FakeMessage()
        finish_reason = "stop"

    class FakeUsage:
        prompt_tokens = 100
        completion_tokens = 50

    class FakeResponse:
        choices = [FakeChoice()]
        usage = FakeUsage()

    def fake_completion(**kwargs):
        captured["messages"] = kwargs["messages"]
        return FakeResponse()

    monkeypatch.setattr("app.services.litellm_provider.litellm.completion", fake_completion)

    result = provider.complete(
        transcription="Now estimate the second scope.",
        system_prompt="SYSTEM",
        tier="flash",
        history=[
            ConversationTurn(role="user", content="Previous scope"),
            ConversationTurn(role="assistant", content="Previous estimate"),
        ],
        max_history_turns=2,
    )

    assert result["estimation"] == "## Estimate with history"
    assert captured["messages"][0] == {"role": "system", "content": "SYSTEM"}
    assert captured["messages"][1] == {"role": "user", "content": "Previous scope"}
    assert captured["messages"][2] == {"role": "assistant", "content": "Previous estimate"}
    assert captured["messages"][-1] == {
        "role": "user",
        "content": "TRANSCRIPCION DE REUNION:\nNow estimate the second scope.",
    }


def test_litellm_provider_stream_accepts_conversation_history(monkeypatch):
    provider = LiteLLMProvider()
    captured = {}

    class FakeDelta:
        content = "hello"

    class FakeChoice:
        delta = FakeDelta()

    class FakeChunk:
        choices = [FakeChoice()]

    def fake_completion(**kwargs):
        captured["messages"] = kwargs["messages"]
        return [FakeChunk()]

    monkeypatch.setattr("app.services.litellm_provider.litellm.completion", fake_completion)

    chunks = list(
        provider.stream(
            transcription="Now estimate the second scope.",
            system_prompt="SYSTEM",
            tier="flash",
            history=[
                ConversationTurn(role="user", content="Previous scope"),
                ConversationTurn(role="assistant", content="Previous estimate"),
            ],
            max_history_turns=2,
        )
    )

    assert chunks == ["hello"]
    assert captured["messages"][0] == {"role": "system", "content": "SYSTEM"}
    assert captured["messages"][1] == {"role": "user", "content": "Previous scope"}
    assert captured["messages"][2] == {"role": "assistant", "content": "Previous estimate"}
    assert captured["messages"][-1] == {
        "role": "user",
        "content": "TRANSCRIPCION DE REUNION:\nNow estimate the second scope.",
    }
