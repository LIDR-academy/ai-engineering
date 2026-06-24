from fastapi.testclient import TestClient

from app.main import app
from app.middleware.logging import record_call_metrics


def test_metrics_endpoint_exposes_rich_last_call_metrics():
    client = TestClient(app)

    client.get("/health")

    record_call_metrics(
        {
            "model": "deepseek-v4-flash",
            "tier": "flash",
            "provider": "deepseek",
            "input_tokens": 100,
            "output_tokens": 50,
            "timestamp": "2026-05-10T00:00:00+00:00",
            "cached": True,
            "cache_backend": "redis",
            "fallback_used": False,
            "finish_reason": "stop",
            "error_type": None,
        }
    )

    response = client.get("/metrics")

    assert response.status_code == 200

    metrics = response.json()

    assert metrics["endpoint"] == "/health"
    assert isinstance(metrics["request_id"], str)
    assert len(metrics["request_id"]) > 8
    assert isinstance(metrics["latency_ms"], int)
    assert metrics["model"] == "deepseek-v4-flash"
    assert metrics["tier"] == "flash"
    assert metrics["provider"] == "deepseek"
    assert metrics["input_tokens"] == 100
    assert metrics["output_tokens"] == 50
    assert metrics["cached"] is True
    assert metrics["cache_backend"] == "redis"
    assert metrics["fallback_used"] is False
    assert metrics["finish_reason"] == "stop"
    assert metrics["error_type"] is None
