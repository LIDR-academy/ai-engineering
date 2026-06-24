from app.middleware.logging import (
    get_last_metrics,
    record_call_metrics,
    record_request_metrics,
)


def test_request_metrics_are_merged_into_last_call_metrics():
    record_request_metrics(
        request_id="req-abc-123",
        endpoint="/api/v1/estimate",
        latency_ms=321,
    )

    record_call_metrics(
        {
            "model": "deepseek-v4-flash",
            "tier": "flash",
            "provider": "deepseek",
            "input_tokens": 100,
            "output_tokens": 50,
            "timestamp": "2026-05-10T00:00:00+00:00",
            "cached": False,
            "cache_backend": "redis",
        }
    )

    metrics = get_last_metrics()

    assert metrics["request_id"] == "req-abc-123"
    assert metrics["endpoint"] == "/api/v1/estimate"
    assert metrics["latency_ms"] == 321
    assert metrics["model"] == "deepseek-v4-flash"
    assert metrics["cache_backend"] == "redis"
