from app.middleware.logging import get_last_metrics, record_call_metrics


def test_record_call_metrics_exposes_cache_backend():
    record_call_metrics(
        {
            "model": "deepseek-v4-flash",
            "tier": "flash",
            "provider": "deepseek",
            "input_tokens": 10,
            "output_tokens": 20,
            "timestamp": "2026-05-10T00:00:00+00:00",
            "cached": True,
            "cache_backend": "redis",
        }
    )

    metrics = get_last_metrics()

    assert metrics["cached"] is True
    assert metrics["cache_backend"] == "redis"
