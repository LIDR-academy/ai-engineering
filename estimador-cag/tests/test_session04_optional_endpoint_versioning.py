from fastapi.testclient import TestClient

from app.main import app

DESCRIPTION = (
    "Build a partner onboarding SaaS with account approval, role based review, "
    "email notifications, and operational reporting for support managers."
)


def test_endpoint_accepts_prompt_version_query_param(monkeypatch):
    from app.routers import estimations as estimations_router

    calls = {}

    def fake_estimate_product(request, prompt_version="v1"):
        calls["request"] = request
        calls["prompt_version"] = prompt_version
        return {
            "text": "typed v2 estimate",
            "prompt_version": prompt_version,
        }

    monkeypatch.setattr(estimations_router, "estimate_product", fake_estimate_product)

    client = TestClient(app)
    response = client.post(
        "/api/v1/estimate?prompt_version=v2",
        json={
            "description": DESCRIPTION,
            "project_type": "web_saas",
            "detail_level": "detailed",
            "output_format": "phases_table",
            "reference_projects": [
                {
                    "name": "Internal CRM migration",
                    "summary": "Migrated spreadsheet workflows to a SaaS workflow.",
                    "estimated_hours": 260,
                    "notes": "Permissions were the main risk.",
                }
            ],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "text": "typed v2 estimate",
        "prompt_version": "v2",
    }
    assert calls["prompt_version"] == "v2"
    assert calls["request"].reference_projects[0].name == "Internal CRM migration"


def test_typed_validation_error_does_not_report_legacy_transcription_field():
    client = TestClient(app)
    response = client.post(
        "/api/v1/estimate",
        json={
            "description": "Too short",
            "project_type": "web_saas",
            "detail_level": "medium",
            "output_format": "phases_table",
        },
    )

    assert response.status_code == 422
    assert "String should have at least 20 characters" in response.text
    assert "transcription" not in response.text


def test_legacy_transcription_request_still_works_after_manual_dispatch(monkeypatch):
    from app.routers import estimations as estimations_router

    def fake_estimate(transcription, tier=None, history=None, max_history_turns=6):
        return {
            "estimation": f"legacy estimate for {transcription}",
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
            "transcription": "Client wants an internal approval workflow with email notifications.",
            "tier": "flash",
        },
    )

    assert response.status_code == 200
    assert response.json()["estimation"].startswith("legacy estimate")
