import anyio

from app.middleware.logging import get_last_metrics, logging_middleware, record_call_metrics


class FakeURL:
    path = "/api/v1/estimate"


class FakeRequest:
    method = "POST"
    url = FakeURL()


class FakeResponse:
    status_code = 200


async def route_handler_records_llm_metrics_during_call_next(request):
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
    return FakeResponse()


def test_middleware_request_metadata_exists_before_route_records_llm_metrics():
    response = anyio.run(
        logging_middleware,
        FakeRequest(),
        route_handler_records_llm_metrics_during_call_next,
    )

    metrics = get_last_metrics()

    assert response.status_code == 200
    assert metrics["endpoint"] == "/api/v1/estimate"
    assert isinstance(metrics["request_id"], str)
    assert len(metrics["request_id"]) > 8


def test_middleware_updates_last_call_latency_after_route_finishes():
    response = anyio.run(
        logging_middleware,
        FakeRequest(),
        route_handler_records_llm_metrics_during_call_next,
    )

    metrics = get_last_metrics()

    assert response.status_code == 200
    assert metrics["endpoint"] == "/api/v1/estimate"
    assert isinstance(metrics["latency_ms"], int)
    assert metrics["latency_ms"] >= 0
