from fastapi.testclient import TestClient

from app.main import app
from app.middleware.logging import get_last_metrics


class FakeCache:
    backend_name = "redis"

    def __init__(self):
        self.store = {}

    def make_key(self, *, tier, model, system_prompt, transcription):
        return f"stream-metrics:{tier}:{model}:{transcription}"

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value):
        self.store[key] = value


class FakeResolved:
    model = "deepseek-v4-flash"
    provider = "deepseek"


class FakeProvider:
    def resolve_model(self, tier):
        return FakeResolved()


def test_stream_endpoint_records_backend_metrics_on_cache_miss(monkeypatch):
    fake_cache = FakeCache()

    def fake_estimate_stream(transcription, tier=None, history=None, max_history_turns=6):
        yield "Hello "
        yield "stream"

    monkeypatch.setattr("app.routers.estimations.build_redis_cache", lambda: fake_cache)
    monkeypatch.setattr("app.routers.estimations.LiteLLMProvider", lambda: FakeProvider())
    monkeypatch.setattr(
        "app.routers.estimations.estimate_stream",
        fake_estimate_stream,
    )

    client = TestClient(app)

    response = client.post(
        "/api/v1/estimate/stream",
        json={
            "transcription": "Unique stream metrics miss transcript.",
            "tier": "flash",
        },
    )

    assert response.status_code == 200
    assert "event: token" in response.text
    assert "Hello " in response.text
    assert "stream" in response.text

    metrics = get_last_metrics()

    assert metrics["endpoint"] == "/api/v1/estimate/stream"
    assert metrics["model"] == "deepseek-v4-flash"
    assert metrics["provider"] == "deepseek"
    assert metrics["tier"] == "flash"
    assert metrics["cached"] is False
    assert metrics["cache_backend"] == "redis"
    assert metrics["finish_reason"] == "stream_done"
    assert metrics["error_type"] is None


def test_stream_endpoint_records_backend_metrics_on_cache_hit(monkeypatch):
    fake_cache = FakeCache()

    def fake_estimate_stream(transcription, tier=None, history=None, max_history_turns=6):
        yield "Hello "
        yield "stream"

    monkeypatch.setattr("app.routers.estimations.build_redis_cache", lambda: fake_cache)
    monkeypatch.setattr("app.routers.estimations.LiteLLMProvider", lambda: FakeProvider())
    monkeypatch.setattr(
        "app.routers.estimations.estimate_stream",
        fake_estimate_stream,
    )

    client = TestClient(app)
    payload = {
        "transcription": "Unique stream metrics hit transcript.",
        "tier": "flash",
    }

    client.post("/api/v1/estimate/stream", json=payload)
    second = client.post("/api/v1/estimate/stream", json=payload)

    assert second.status_code == 200

    metrics = get_last_metrics()

    assert metrics["endpoint"] == "/api/v1/estimate/stream"
    assert metrics["model"] == "deepseek-v4-flash"
    assert metrics["provider"] == "deepseek"
    assert metrics["tier"] == "flash"
    assert metrics["cached"] is True
    assert metrics["cache_backend"] == "redis"
    assert metrics["error_type"] is None
