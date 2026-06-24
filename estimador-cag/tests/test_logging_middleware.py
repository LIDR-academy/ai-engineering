import anyio

from app.middleware.logging import get_last_metrics, logging_middleware, record_call_metrics


class FakeURL:
    path = "/api/v1/estimate"


class FakeRequest:
    method = "POST"
    url = FakeURL()


class FakeResponse:
    status_code = 200


async def fake_call_next(request):
    return FakeResponse()


def test_logging_middleware_records_request_metadata():
    response = anyio.run(logging_middleware, FakeRequest(), fake_call_next)

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

    assert response.status_code == 200
    assert metrics["endpoint"] == "/api/v1/estimate"
    assert isinstance(metrics["request_id"], str)
    assert len(metrics["request_id"]) > 8
    assert isinstance(metrics["latency_ms"], int)
    assert metrics["latency_ms"] >= 0
