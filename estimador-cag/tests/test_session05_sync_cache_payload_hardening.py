from fastapi.testclient import TestClient

from app.main import app
from app.routers import estimations as estimations_router


def test_sync_estimate_normalizes_stream_shaped_cached_payload(monkeypatch):
    stream_shaped_cached_payload = {
        "cost_source": "missing_token_usage",
        "cost_usd": None,
        "estimation": "Legacy streamed markdown estimate from Redis",
        "fallback_used": False,
        "finish_reason": "stream_done",
        "input_tokens": None,
        "model": "deepseek-v4-flash",
        "output_tokens": None,
        "pricing_model": "deepseek-v4-flash",
        "provider": "deepseek",
        "tier": "flash",
        "cached": True,
        "cache_backend": "redis",
    }

    monkeypatch.setattr(
        estimations_router,
        "estimate_product",
        lambda request, **kwargs: stream_shaped_cached_payload,
    )

    client = TestClient(app)
    response = client.post(
        "/api/v1/estimate?prompt_version=v1",
        json={
            "description": "Build a small onboarding platform with FastAPI and PostgreSQL.",
            "project_type": "web_saas",
            "detail_level": "summary",
            "output_format": "phases_table",
            "tier": "flash",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["text"] == "Legacy streamed markdown estimate from Redis"
    assert payload["prompt_version"] == "v1"
