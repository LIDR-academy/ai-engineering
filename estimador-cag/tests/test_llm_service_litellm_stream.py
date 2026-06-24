from app.services import llm_service


class FakeLiteLLMProvider:
    def __init__(self):
        self.calls = []

    def stream(
        self,
        *,
        transcription,
        system_prompt,
        tier,
        max_tokens=2000,
        history=None,
        max_history_turns=6,
    ):
        self.calls.append(
            {
                "transcription": transcription,
                "system_prompt": system_prompt,
                "tier": tier,
                "max_tokens": max_tokens,
                "history": history,
                "max_history_turns": max_history_turns,
            }
        )
        yield "Hello "
        yield "stream"


def test_estimate_stream_uses_litellm_provider(monkeypatch):
    fake_provider = FakeLiteLLMProvider()

    monkeypatch.setattr(llm_service, "LiteLLMProvider", lambda: fake_provider)

    chunks = list(
        llm_service.estimate_stream(
            transcription="Build a landing page",
            tier="flash",
        )
    )

    assert chunks == ["Hello ", "stream"]
    assert fake_provider.calls
    assert fake_provider.calls[0]["tier"] == "flash"
    assert fake_provider.calls[0]["max_tokens"] == 2000
