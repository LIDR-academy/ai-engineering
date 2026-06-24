from fastapi.testclient import TestClient

from app.main import app
from app.middleware.logging import get_last_metrics


class FakeCache:
    backend_name = "redis"

    def __init__(self):
        self.store = {}

    def make_key(self, *, tier, model, system_prompt, transcription):
        return f"stream:{tier}:{model}:{transcription}"

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value):
        self.store[key] = value


def test_stream_endpoint_uses_redis_cache_for_repeated_streams(monkeypatch):
    fake_cache = FakeCache()
    provider_calls = {"count": 0}

    class FakeResolved:
        model = "deepseek-v4-flash"
        provider = "deepseek"

    class FakeProvider:
        def resolve_model(self, tier):
            return FakeResolved()

    def fake_estimate_stream(transcription, tier=None, history=None, max_history_turns=6):
        provider_calls["count"] += 1
        yield "Hello "
        yield "stream"

    monkeypatch.setattr("app.routers.estimations.build_redis_cache", lambda: fake_cache)
    monkeypatch.setattr("app.routers.estimations.LiteLLMProvider", lambda: FakeProvider())
    monkeypatch.setattr("app.routers.estimations.estimate_stream", fake_estimate_stream)

    client = TestClient(app)
    payload = {
        "transcription": "We need a landing page, blog, CRM integration and testing.",
        "tier": "flash",
    }

    first = client.post("/api/v1/estimate/stream", json=payload)
    first_metrics = get_last_metrics()

    second = client.post("/api/v1/estimate/stream", json=payload)
    second_metrics = get_last_metrics()

    assert first.status_code == 200
    assert second.status_code == 200

    assert "Hello " in first.text
    assert "stream" in first.text
    assert "Hello stream" in second.text or "Hello " in second.text

    assert provider_calls["count"] == 1

    assert first_metrics["cached"] is False
    assert first_metrics["cache_backend"] == "redis"

    assert second_metrics["cached"] is True
    assert second_metrics["cache_backend"] == "redis"
