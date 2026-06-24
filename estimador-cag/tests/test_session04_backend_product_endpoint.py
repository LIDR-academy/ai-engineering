from fastapi.testclient import TestClient

from app.main import app
from app.schemas.estimation import EstimationRequest

VALID_DESCRIPTION = (
    "Build a customer onboarding SaaS with authentication, admin approval, "
    "email notifications, and a reporting dashboard for operations managers."
)


def test_session04_estimate_endpoint_accepts_typed_product_request(monkeypatch):
    from app.routers import estimations as estimations_router

    calls = {}

    def fake_estimate_product(request: EstimationRequest, prompt_version="v1"):
        calls["request"] = request
        return {
            "text": "## Product estimate\n\nTyped estimate from fake product service.",
            "prompt_version": "v1",
        }

    monkeypatch.setattr(estimations_router, "estimate_product", fake_estimate_product)

    client = TestClient(app)
    response = client.post(
        "/api/v1/estimate",
        json={
            "description": VALID_DESCRIPTION,
            "project_type": "web_saas",
            "detail_level": "medium",
            "output_format": "phases_table",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "text": "## Product estimate\n\nTyped estimate from fake product service.",
        "prompt_version": "v1",
    }
    assert response.json()["prompt_version"] == "v1"
    assert calls["request"].description == VALID_DESCRIPTION
    assert calls["request"].project_type == "web_saas"
    assert calls["request"].detail_level == "medium"
    assert calls["request"].output_format == "phases_table"


def test_session04_estimate_endpoint_still_accepts_legacy_transcription_request(monkeypatch):
    from app.routers import estimations as estimations_router

    def fake_estimate(transcription, tier=None, history=None, max_history_turns=6):
        return {
            "estimation": "## Legacy estimate",
            "model": "deepseek-v4-flash",
            "tier": tier or "flash",
            "provider": "deepseek",
            "input_tokens": 10,
            "output_tokens": 20,
            "timestamp": "2026-05-12T00:00:00+00:00",
            "cached": False,
            "cache_backend": "redis",
            "cost_usd": 0.0001,
            "cost_source": "static_estimate",
            "pricing_model": "deepseek-v4-flash",
        }

    monkeypatch.setattr(estimations_router, "estimate", fake_estimate)

    client = TestClient(app)
    response = client.post(
        "/api/v1/estimate",
        json={
            "transcription": "Client wants a landing page with a CRM integration.",
            "tier": "flash",
        },
    )

    assert response.status_code == 200
    assert response.json()["estimation"] == "## Legacy estimate"
