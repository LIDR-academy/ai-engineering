from fastapi.testclient import TestClient

from app.main import app
from app.schemas.estimation import EstimateRequest


def test_estimate_request_accepts_conversation_history():
    request = EstimateRequest(
        transcription="Current meeting transcript",
        tier="flash",
        history=[
            {"role": "user", "content": "Previous user message"},
            {"role": "assistant", "content": "Previous assistant estimate"},
        ],
        max_history_turns=2,
    )

    dumped = request.model_dump()

    assert dumped["history"][0]["role"] == "user"
    assert dumped["history"][1]["role"] == "assistant"
    assert dumped["max_history_turns"] == 2


def test_estimate_endpoint_passes_history_to_service(monkeypatch):
    captured = {}

    def fake_estimate(transcription, tier=None, history=None, max_history_turns=6):
        captured["transcription"] = transcription
        captured["tier"] = tier
        captured["history"] = history
        captured["max_history_turns"] = max_history_turns
        return {
            "estimation": "## Estimate with API history",
            "model": "deepseek-v4-flash",
            "tier": "flash",
            "provider": "deepseek",
            "input_tokens": 10,
            "output_tokens": 20,
            "timestamp": "2026-05-10T00:00:00+00:00",
            "cached": False,
            "cache_backend": "redis",
            "cost_usd": 0.0001,
            "cost_source": "static_estimate",
            "pricing_model": "deepseek-v4-flash",
        }

    monkeypatch.setattr("app.routers.estimations.estimate", fake_estimate)

    client = TestClient(app)

    response = client.post(
        "/api/v1/estimate",
        json={
            "transcription": "Current meeting transcript",
            "tier": "flash",
            "history": [
                {"role": "user", "content": "Previous user message"},
                {"role": "assistant", "content": "Previous assistant estimate"},
            ],
            "max_history_turns": 2,
        },
    )

    assert response.status_code == 200
    assert captured["transcription"] == "Current meeting transcript"
    assert captured["tier"] == "flash"
    assert captured["history"][0].role == "user"
    assert captured["history"][1].role == "assistant"
    assert captured["max_history_turns"] == 2


def test_stream_endpoint_passes_history_to_service(monkeypatch):
    captured = {}

    class FakeCache:
        backend_name = "redis"

        def make_key(self, *, tier, model, system_prompt, transcription):
            return "api-history-stream-key"

        def get(self, key):
            return None

        def set(self, key, value):
            pass

    class FakeResolved:
        model = "deepseek-v4-flash"
        provider = "deepseek"

    class FakeProvider:
        def resolve_model(self, tier):
            return FakeResolved()

    def fake_estimate_stream(transcription, tier=None, history=None, max_history_turns=6):
        captured["transcription"] = transcription
        captured["tier"] = tier
        captured["history"] = history
        captured["max_history_turns"] = max_history_turns
        yield "hello"

    monkeypatch.setattr("app.routers.estimations.build_redis_cache", lambda: FakeCache())
    monkeypatch.setattr("app.routers.estimations.LiteLLMProvider", lambda: FakeProvider())
    monkeypatch.setattr("app.routers.estimations.estimate_stream", fake_estimate_stream)

    client = TestClient(app)

    response = client.post(
        "/api/v1/estimate/stream",
        json={
            "transcription": "Current meeting transcript",
            "tier": "flash",
            "history": [
                {"role": "user", "content": "Previous user message"},
                {"role": "assistant", "content": "Previous assistant estimate"},
            ],
            "max_history_turns": 2,
        },
    )

    assert response.status_code == 200
    assert "hello" in response.text
    assert captured["transcription"] == "Current meeting transcript"
    assert captured["tier"] == "flash"
    assert captured["history"][0].role == "user"
    assert captured["history"][1].role == "assistant"
    assert captured["max_history_turns"] == 2
