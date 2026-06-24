from app.middleware.logging import get_last_metrics, record_call_metrics


def test_record_call_metrics_exposes_phase_3_observability_contract():
    record_call_metrics(
        {
            "request_id": "req-test-123",
            "endpoint": "/api/v1/estimate",
            "model": "deepseek-v4-flash",
            "tier": "flash",
            "provider": "deepseek",
            "input_tokens": 100,
            "output_tokens": 50,
            "latency_ms": 1234,
            "cost_usd": 0.0012,
            "cached": False,
            "cache_backend": "redis",
            "fallback_used": False,
            "finish_reason": "stop",
            "error_type": None,
            "timestamp": "2026-05-10T00:00:00+00:00",
        }
    )

    metrics = get_last_metrics()

    assert metrics["request_id"] == "req-test-123"
    assert metrics["endpoint"] == "/api/v1/estimate"
    assert metrics["model"] == "deepseek-v4-flash"
    assert metrics["tier"] == "flash"
    assert metrics["provider"] == "deepseek"
    assert metrics["input_tokens"] == 100
    assert metrics["output_tokens"] == 50
    assert metrics["latency_ms"] == 1234
    assert metrics["cost_usd"] == 0.0012
    assert metrics["cached"] is False
    assert metrics["cache_backend"] == "redis"
    assert metrics["fallback_used"] is False
    assert metrics["finish_reason"] == "stop"
    assert metrics["error_type"] is None
    assert metrics["timestamp"] == "2026-05-10T00:00:00+00:00"


def test_record_call_metrics_preserves_cost_metadata():
    record_call_metrics(
        {
            "request_id": "req-cost-123",
            "endpoint": "/api/v1/estimate",
            "model": "deepseek-v4-flash",
            "tier": "flash",
            "provider": "deepseek",
            "input_tokens": 1000,
            "output_tokens": 2000,
            "latency_ms": 321,
            "cost_usd": 0.00247,
            "cost_source": "static_estimate",
            "pricing_model": "deepseek-v4-flash",
            "cached": False,
            "cache_backend": "redis",
            "fallback_used": False,
            "finish_reason": "stop",
            "error_type": None,
            "timestamp": "2026-05-10T00:00:00+00:00",
        }
    )

    metrics = get_last_metrics()

    assert metrics["cost_usd"] == 0.00247
    assert metrics["cost_source"] == "static_estimate"
    assert metrics["pricing_model"] == "deepseek-v4-flash"
