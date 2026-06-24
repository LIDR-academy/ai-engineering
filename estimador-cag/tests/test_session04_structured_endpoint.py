import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.estimation import EstimationRequest, EstimationResult
from app.services import llm_service

VALID_DESCRIPTION = (
    "Build a B2B onboarding SaaS with account approval, role based admin review, "
    "email notifications, and an operations reporting dashboard."
)


def structured_payload(total_cost_eur: int = 9000) -> dict:
    """
    Valid structured estimate payload used by fake providers.

    Why this matters:
    Phase 4 must prove that the typed product path now returns data fields,
    not markdown that the frontend must parse.
    """

    return {
        "summary": "A structured estimate for a B2B onboarding SaaS.",
        "project_type": "web_saas",
        "detail_level": "medium",
        "output_format": "phases_table",
        "total_duration_weeks": 4,
        "total_cost_eur": total_cost_eur,
        "confidence_pct": 78,
        "phases": [
            {
                "name": "Discovery",
                "summary": "Clarify workflow, roles, reporting, and notification scope.",
                "duration_weeks": 2,
                "cost_eur": 4000,
                "confidence_pct": 82,
                "tasks": ["Interview stakeholders", "Define roles", "Confirm reporting needs"],
                "risks": ["Approval workflow may expand"],
            },
            {
                "name": "Implementation",
                "summary": "Build backend, product UI, notifications, and reporting dashboard.",
                "duration_weeks": 2,
                "cost_eur": 5000,
                "confidence_pct": 76,
                "tasks": ["Build API", "Build UI", "Add notifications", "Add reports"],
                "risks": ["Email template details may change"],
            },
        ],
        "assumptions": ["Authentication is email and password only"],
        "risks": ["Reporting scope may grow"],
        "recommendations": ["Confirm approval states before implementation"],
    }


class FakeCache:
    """
    Exact cache fake that records cache identity and stored values.

    Why this matters:
    Phase 4 must prove exact cache still runs before semantic cache work and
    that invalid structured output is never cached.
    """

    backend_name = "redis"

    def __init__(self):
        self.store = {}
        self.key_inputs = []
        self.get_calls = []

    def make_key(self, *, tier, model, system_prompt, transcription):
        self.key_inputs.append(
            {
                "tier": tier,
                "model": model,
                "system_prompt": system_prompt,
                "transcription": transcription,
            }
        )
        return f"key-{len(self.key_inputs)}"

    def get(self, key):
        self.get_calls.append(key)
        return self.store.get(key)

    def set(self, key, value):
        self.store[key] = value


class FakeStructuredProvider:
    """
    Structured provider fake used by service tests.

    Why this matters:
    The service should call the structured provider path from Phase 3 and then
    normalize metadata for the API response.
    """

    def __init__(self, payload=None):
        self.calls = []
        self.payload = payload or structured_payload()

    def resolve_model(self, tier):
        class Resolved:
            model = "deepseek-v4-flash"

        return Resolved()

    def complete_structured_messages_with_fallback(
        self,
        *,
        messages,
        starting_tier,
        tier_ladder,
        response_model,
        max_tokens=2000,
    ):
        self.calls.append(
            {
                "messages": messages,
                "starting_tier": starting_tier,
                "tier_ladder": tier_ladder,
                "response_model": response_model,
                "max_tokens": max_tokens,
            }
        )
        return {
            "result": self.payload,
            "model": "deepseek-v4-flash",
            "tier": starting_tier,
            "provider": "deepseek",
            "input_tokens": 10,
            "output_tokens": 20,
            "cost_usd": 0.0001,
            "cost_source": "static_estimate",
            "pricing_model": "deepseek-v4-flash",
            "finish_reason": "stop",
            "fallback_used": False,
            "timestamp": "2026-05-16T00:00:00+00:00",
        }


def make_request(reference_projects=None) -> EstimationRequest:
    return EstimationRequest(
        description=VALID_DESCRIPTION,
        project_type="web_saas",
        detail_level="medium",
        output_format="phases_table",
        reference_projects=reference_projects,
    )


def install_service_fakes(monkeypatch, *, payload=None):
    fake_cache = FakeCache()
    fake_provider = FakeStructuredProvider(payload=payload)

    def fake_render_estimation_prompt(received_request, version="v1"):
        return (
            f"system prompt for {version} and {received_request.project_type}",
            f"user prompt for {version}: {received_request.description}",
        )

    monkeypatch.setattr(llm_service, "build_redis_cache", lambda: fake_cache)
    monkeypatch.setattr(llm_service, "LiteLLMProvider", lambda: fake_provider)
    monkeypatch.setattr(llm_service, "render_estimation_prompt", fake_render_estimation_prompt)

    return fake_cache, fake_provider


def test_typed_request_returns_structured_result_summary_and_phases(monkeypatch):
    """
    The typed product path must return result.summary and result.phases.

    Why this matters:
    Streamlit should render fields instead of parsing prose.
    """

    fake_cache, fake_provider = install_service_fakes(monkeypatch)

    response = llm_service.estimate_product(make_request(), prompt_version="v2")

    assert response["prompt_version"] == "v2"
    assert isinstance(response["result"], EstimationResult)
    assert response["result"].summary == "A structured estimate for a B2B onboarding SaaS."
    assert len(response["result"].phases) == 2
    assert response["result"].total_cost_eur == 9000
    assert "text" in response
    assert fake_provider.calls[0]["response_model"] is EstimationResult
    assert fake_cache.store


def test_prompt_version_query_param_returns_v2(monkeypatch):
    """
    The endpoint must forward prompt_version=v2 to the product service.

    Why this matters:
    Prompt versioning is part of the exact cache identity and audit trail.
    """

    from app.routers import estimations as estimations_router

    calls = {}

    def fake_estimate_product(request, prompt_version="v1"):
        calls["prompt_version"] = prompt_version
        return {
            "prompt_version": prompt_version,
            "result": structured_payload(),
            "text": "structured v2 text",
            "cached": False,
            "cache_backend": "redis",
            "model": "deepseek-v4-flash",
            "provider": "deepseek",
            "tier": "flash",
        }

    monkeypatch.setattr(estimations_router, "estimate_product", fake_estimate_product)

    client = TestClient(app)
    response = client.post(
        "/api/v1/estimate?prompt_version=v2",
        json={
            "description": VALID_DESCRIPTION,
            "project_type": "web_saas",
            "detail_level": "medium",
            "output_format": "phases_table",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert calls["prompt_version"] == "v2"
    assert payload["prompt_version"] == "v2"
    assert payload["result"]["summary"] == "A structured estimate for a B2B onboarding SaaS."


def test_validation_error_for_short_typed_description_does_not_mention_legacy_transcription():
    """
    Invalid typed requests should not show legacy transcription errors.

    Why this matters:
    The manual discriminator keeps product users away from confusing union errors.
    """

    client = TestClient(app)
    response = client.post(
        "/api/v1/estimate",
        json={
            "description": "too short",
            "project_type": "web_saas",
            "detail_level": "medium",
            "output_format": "phases_table",
        },
    )

    assert response.status_code == 422
    assert "transcription" not in response.text.lower()


def test_legacy_transcription_request_still_works(monkeypatch):
    """
    The legacy Session 03 transcription path must remain intact.

    Why this matters:
    Structured product output is additive. It should not break the old API path.
    """

    from app.routers import estimations as estimations_router

    def fake_estimate(transcription, tier=None, history=None, max_history_turns=6):
        return {
            "estimation": "## Legacy estimate",
            "model": "deepseek-v4-flash",
            "tier": tier or "flash",
            "provider": "deepseek",
            "input_tokens": 10,
            "output_tokens": 20,
            "timestamp": "2026-05-16T00:00:00+00:00",
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
            "transcription": "Client wants a landing page with CRM integration.",
            "tier": "flash",
        },
    )

    assert response.status_code == 200
    assert response.json()["estimation"] == "## Legacy estimate"


def test_invalid_structured_result_is_not_cached(monkeypatch):
    """
    Invalid structured model output must not be cached.

    Why this matters:
    The cache should only store trusted Pydantic validated product estimates.
    """

    invalid = structured_payload(total_cost_eur=12345)
    fake_cache, _fake_provider = install_service_fakes(monkeypatch, payload=invalid)

    with pytest.raises(ValueError):
        llm_service.estimate_product(make_request(), prompt_version="v2")

    assert fake_cache.store == {}


def test_prompt_version_influences_exact_cache_key(monkeypatch):
    """
    prompt_version must influence exact cache identity.

    Why this matters:
    v1 and v2 prompts can produce different estimates for the same request.
    """

    fake_cache, _fake_provider = install_service_fakes(monkeypatch)
    request = make_request()

    llm_service.estimate_product(request, prompt_version="v1")
    llm_service.estimate_product(request, prompt_version="v2")

    prompts = [entry["system_prompt"] for entry in fake_cache.key_inputs]

    assert "prompt_version=v1" in prompts[0]
    assert "prompt_version=v2" in prompts[1]
    assert prompts[0] != prompts[1]


def test_reference_projects_influence_exact_cache_key(monkeypatch):
    """
    reference_projects must influence exact cache identity.

    Why this matters:
    Similar project context changes the estimate and must not reuse another cache entry.
    """

    fake_cache, _fake_provider = install_service_fakes(monkeypatch)

    request_without_refs = make_request()
    request_with_refs = make_request(
        reference_projects=[
            {
                "name": "CRM migration",
                "summary": "Moved spreadsheet workflows to a role based SaaS.",
                "estimated_hours": 260,
                "notes": "Permissions and reporting were the main risks.",
            }
        ]
    )

    llm_service.estimate_product(request_without_refs, prompt_version="v2")
    llm_service.estimate_product(request_with_refs, prompt_version="v2")

    transcriptions = [entry["transcription"] for entry in fake_cache.key_inputs]

    assert transcriptions[0] != transcriptions[1]
    assert "CRM migration" in transcriptions[1]


def test_metadata_includes_prompt_cache_model_provider_and_tier(monkeypatch):
    """
    Structured response should expose operational metadata when available.

    Why this matters:
    The product is easier to audit when users can see prompt version, cache state,
    model, provider, and tier.
    """

    install_service_fakes(monkeypatch)

    response = llm_service.estimate_product(make_request(), prompt_version="v2")

    assert response["prompt_version"] == "v2"
    assert response["cached"] is False
    assert response["cache_backend"] == "redis"
    assert response["model"] == "deepseek-v4-flash"
    assert response["provider"] == "deepseek"
    assert response["tier"] == "flash"


def test_structured_endpoint_exposes_fallback_observability_metadata(monkeypatch):
    """
    The HTTP API must not strip fallback metadata from structured responses.

    Why this matters:
    FastAPI response_model filtering can silently remove newly-added service
    fields unless the response schema exposes them. The product UI and auditors
    need to know whether the request was served by DeepSeek or a Kimi fallback.
    """

    from app.routers import estimations as estimations_router

    def fake_estimate_product(request, prompt_version="v1"):
        return {
            "text": "fallback estimate",
            "prompt_version": prompt_version,
            "model": "moonshot/kimi-k2.6",
            "provider": "kimi",
            "tier": "backup_pro",
            "requested_tier": "flash",
            "served_tier": "backup_pro",
            "fallback_used": True,
            "result": {
                "summary": "A fallback estimate.",
                "project_type": "web_saas",
                "detail_level": "medium",
                "output_format": "phases_table",
                "total_duration_weeks": 2,
                "total_cost_eur": 3000,
                "confidence_pct": 80,
                "phases": [
                    {
                        "name": "Implementation",
                        "summary": "Build the first version.",
                        "duration_weeks": 2,
                        "cost_eur": 3000,
                        "confidence_pct": 80,
                        "tasks": ["Build backend"],
                        "risks": [],
                    }
                ],
                "assumptions": [],
                "risks": [],
                "recommendations": [],
            },
        }

    monkeypatch.setattr(estimations_router, "estimate_product", fake_estimate_product)

    response = TestClient(app).post(
        "/api/v1/estimate?prompt_version=v2",
        json={
            "description": "Build a B2B onboarding SaaS with approval workflow and reports.",
            "project_type": "web_saas",
            "detail_level": "medium",
            "output_format": "phases_table",
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert body["requested_tier"] == "flash"
    assert body["served_tier"] == "backup_pro"
    assert body["fallback_used"] is True
    assert body["provider"] == "kimi"
    assert body["tier"] == "backup_pro"
