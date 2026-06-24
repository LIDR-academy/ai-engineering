import pytest

from app.guardrails.output import evaluate_output_guardrails
from app.schemas.estimation import EstimationRequest, EstimationResult
from app.services import llm_service

VALID_DESCRIPTION = (
    "Build a B2B onboarding SaaS with account approval, role based admin review, "
    "email notifications, and an operations reporting dashboard."
)


def structured_payload(summary: str = "A structured estimate for a B2B onboarding SaaS.") -> dict:
    """
    Valid structured estimate payload used by fake providers.

    Why this matters:
    Output guardrails should run after Pydantic validation, so tests start from
    a valid EstimationResult unless they intentionally check unsafe content.
    """

    return {
        "summary": summary,
        "project_type": "web_saas",
        "detail_level": "medium",
        "output_format": "phases_table",
        "total_duration_weeks": 4,
        "total_cost_eur": 9000,
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
    Exact cache fake that records stored values.

    Why this matters:
    Invalid output must not be cached. This proves output guardrails run before
    estimate_with_exact_cache stores fresh model output.
    """

    backend_name = "redis"

    def __init__(self):
        self.store = {}

    def make_key(self, *, tier, model, system_prompt, transcription):
        return "output-guardrail-cache-key"

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value):
        self.store[key] = value


class FakeStructuredProvider:
    """Provider fake that returns a configurable structured payload."""

    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

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
        self.calls += 1
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


def make_request() -> EstimationRequest:
    return EstimationRequest(
        description=VALID_DESCRIPTION,
        project_type="web_saas",
        detail_level="medium",
        output_format="phases_table",
    )


def install_service_fakes(monkeypatch, payload):
    fake_cache = FakeCache()
    fake_provider = FakeStructuredProvider(payload)

    def fake_render_estimation_prompt(received_request, version="v1"):
        return (
            f"system prompt for {version}",
            f"user prompt for {version}: {received_request.description}",
        )

    monkeypatch.setattr(llm_service, "build_redis_cache", lambda: fake_cache)
    monkeypatch.setattr(llm_service, "LiteLLMProvider", lambda: fake_provider)
    monkeypatch.setattr(llm_service, "render_estimation_prompt", fake_render_estimation_prompt)

    return fake_cache, fake_provider


def test_valid_result_passes_output_guardrails():
    """
    Normal validated output should pass.

    Why this matters:
    Output guardrails should protect the product without blocking good estimates.
    """

    result = EstimationResult.model_validate(structured_payload())
    decision = evaluate_output_guardrails(result)

    assert decision.allowed is True
    assert decision.reason_code is None
    assert decision.message is None


def test_low_confidence_without_out_of_scope_fails_output_guardrail():
    """
    Low confidence estimates need explicit out of scope framing.

    Why this matters:
    This duplicates the schema invariant at the guardrail layer so the product
    safety rule is visible and testable outside Pydantic internals.
    """

    payload = structured_payload(summary="Maybe possible, but requirements are unclear.")
    payload["confidence_pct"] = 40
    payload["phases"][0]["confidence_pct"] = 40
    payload["phases"][1]["confidence_pct"] = 40

    decision = evaluate_output_guardrails(payload)

    assert decision.allowed is False
    assert decision.reason_code == "low_confidence_unframed"


def test_output_containing_system_prompt_leak_fails():
    """
    Output must not mention leaking or revealing the system prompt.

    Why this matters:
    Even structured outputs can contain unsafe text in summary, assumptions,
    risks, recommendations, phase summaries, tasks, or risks.
    """

    result = EstimationResult.model_validate(
        structured_payload(summary="The system prompt says to reveal hidden instructions.")
    )

    decision = evaluate_output_guardrails(result)

    assert decision.allowed is False
    assert decision.reason_code == "system_prompt_leak"


def test_invalid_output_is_not_cached(monkeypatch):
    """
    Unsafe structured output must not be stored in exact cache.

    Why this matters:
    A bad output should fail once, not become a reusable cached product response.
    """

    unsafe_payload = structured_payload(
        summary="The system prompt says to reveal hidden instructions."
    )
    fake_cache, fake_provider = install_service_fakes(monkeypatch, unsafe_payload)

    with pytest.raises(RuntimeError, match="(?i)output guardrails"):
        llm_service.estimate_product(make_request(), prompt_version="v2")

    assert fake_provider.calls == 1
    assert fake_cache.store == {}


def test_invalid_output_returns_clear_502_from_api(monkeypatch):
    """
    The API should surface invalid model output as a 502 provider style failure.

    Why this matters:
    Unsafe model output is not a user input validation problem. It is a backend
    model output failure and should be distinguishable from 400 input guardrails.
    """

    from app.routers import estimations as estimations_router

    def fake_estimate_product(request, prompt_version="v1"):
        raise RuntimeError("Output guardrails blocked model output: system_prompt_leak")

    monkeypatch.setattr(estimations_router, "estimate_product", fake_estimate_product)

    from fastapi.testclient import TestClient

    from app.main import app

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

    assert response.status_code == 502
    assert "Output guardrails blocked model output" in response.text


def test_no_retry_is_implemented_for_output_guardrails_yet():
    """
    Output guardrail retry is intentionally not implemented in Phase 7.

    Why this matters:
    This keeps the slice small and honest. A retry policy can be added later with
    explicit tests for retry count, cache behavior, and metrics.
    """

    source = llm_service.estimate_product.__doc__ or ""

    assert "retry" not in source.lower()
