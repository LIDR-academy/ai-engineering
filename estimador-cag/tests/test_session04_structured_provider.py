import json

import pytest

from app.schemas.estimation import EstimationResult, ProjectType
from app.services.litellm_provider import LiteLLMProvider


def structured_payload() -> dict:
    """
    Valid structured estimate returned by a fake LLM.

    Why this matters:
    The provider should validate model output into EstimationResult before any
    router, service, UI, or cache code trusts the payload.
    """

    return {
        "summary": "A structured estimate for a SaaS onboarding product.",
        "project_type": "web_saas",
        "detail_level": "medium",
        "output_format": "phases_table",
        "total_duration_weeks": 4,
        "total_cost_eur": 9000,
        "confidence_pct": 75,
        "phases": [
            {
                "name": "Discovery",
                "summary": "Clarify requirements and delivery risks.",
                "duration_weeks": 2,
                "cost_eur": 4000,
                "confidence_pct": 80,
                "tasks": ["Interview stakeholders", "Define approval workflow"],
                "risks": ["Unclear reporting scope"],
            },
            {
                "name": "Build",
                "summary": "Implement the product workflow and reporting.",
                "duration_weeks": 2,
                "cost_eur": 5000,
                "confidence_pct": 75,
                "tasks": ["Build backend", "Build Streamlit or web UI"],
                "risks": ["Notification details may expand"],
            },
        ],
        "assumptions": ["Email and password authentication only"],
        "risks": ["Reporting scope may grow"],
        "recommendations": ["Confirm approval workflow before build"],
    }


class FakeMessage:
    """Fake LiteLLM message object so tests avoid real API calls."""

    def __init__(self, content):
        self.content = content


class FakeChoice:
    def __init__(self, content, finish_reason="stop"):
        self.message = FakeMessage(content)
        self.finish_reason = finish_reason


class FakeUsage:
    prompt_tokens = 123
    completion_tokens = 456


class FakeResponse:
    def __init__(self, content):
        self.choices = [FakeChoice(content)]
        self.usage = FakeUsage()


def test_complete_structured_messages_sends_exact_messages_and_response_model(monkeypatch):
    """
    Structured calls must preserve exact rendered system and user messages.

    Why this matters:
    Session 04 moved prompt rendering into Jinja2 templates. The provider should
    not rebuild, concatenate, or mutate those messages.
    """

    provider = LiteLLMProvider()
    calls = {}
    messages = [
        {"role": "system", "content": "You are an estimator. Return JSON."},
        {"role": "user", "content": "<project_description>Build SaaS</project_description>"},
    ]

    def fake_completion(**kwargs):
        calls.update(kwargs)
        return FakeResponse(json.dumps(structured_payload()))

    monkeypatch.setattr("app.services.litellm_provider.litellm.completion", fake_completion)

    result = provider.complete_structured_messages(
        messages=messages,
        tier="flash",
        response_model=EstimationResult,
        max_tokens=1500,
    )

    assert calls["messages"][0]["role"] == "system"
    assert calls["messages"][1] == messages[1]
    assert "Return only valid JSON" in calls["messages"][0]["content"]
    assert "JSON schema" in calls["messages"][0]["content"]
    assert calls["model"] == "deepseek-v4-flash"
    assert calls["api_base"] == "https://api.deepseek.com/v1"
    assert calls["temperature"] == 0.3
    assert calls["max_tokens"] == 1500
    assert "response_model" not in calls
    assert calls["response_format"] == {"type": "json_object"}

    assert isinstance(result["result"], EstimationResult)
    assert result["result"].project_type is ProjectType.WEB_SAAS
    assert result["model"] == "deepseek-v4-flash"
    assert result["provider"] == "deepseek"
    assert result["tier"] == "flash"
    assert result["input_tokens"] == 123
    assert result["output_tokens"] == 456
    assert result["finish_reason"] == "stop"


def test_complete_structured_messages_validates_dict_output(monkeypatch):
    """
    The provider should accept dict shaped structured output and validate it.

    Why this matters:
    Different structured output paths can return dictionaries instead of JSON
    strings. The provider boundary normalizes that variety.
    """

    provider = LiteLLMProvider()

    def fake_completion(**kwargs):
        return FakeResponse(structured_payload())

    monkeypatch.setattr("app.services.litellm_provider.litellm.completion", fake_completion)

    result = provider.complete_structured_messages(
        messages=[
            {"role": "system", "content": "Return structured estimate."},
            {"role": "user", "content": "Build onboarding SaaS."},
        ],
        tier="flash",
        response_model=EstimationResult,
    )

    assert isinstance(result["result"], EstimationResult)
    assert result["result"].total_cost_eur == 9000


def test_complete_structured_messages_accepts_already_validated_model(monkeypatch):
    """
    The provider should accept already parsed Pydantic objects.

    Why this matters:
    If Instructor or a future structured mode returns response_model instances
    directly, the rest of the app should not change.
    """

    provider = LiteLLMProvider()
    parsed = EstimationResult.model_validate(structured_payload())

    def fake_completion(**kwargs):
        return FakeResponse(parsed)

    monkeypatch.setattr("app.services.litellm_provider.litellm.completion", fake_completion)

    result = provider.complete_structured_messages(
        messages=[
            {"role": "system", "content": "Return structured estimate."},
            {"role": "user", "content": "Build onboarding SaaS."},
        ],
        tier="flash",
        response_model=EstimationResult,
    )

    assert result["result"] == parsed


def test_complete_structured_messages_raises_clear_runtime_error_on_invalid_payload(monkeypatch):
    """
    Invalid structured output must fail loudly at the provider boundary.

    Why this matters:
    Broken model output must not reach the UI or cache as trusted product data.
    """

    provider = LiteLLMProvider()
    invalid_payload = structured_payload()
    invalid_payload["phases"] = []

    def fake_completion(**kwargs):
        return FakeResponse(json.dumps(invalid_payload))

    monkeypatch.setattr("app.services.litellm_provider.litellm.completion", fake_completion)

    with pytest.raises(RuntimeError, match="Invalid structured payload"):
        provider.complete_structured_messages(
            messages=[
                {"role": "system", "content": "Return structured estimate."},
                {"role": "user", "content": "Build onboarding SaaS."},
            ],
            tier="flash",
            response_model=EstimationResult,
        )


def test_complete_structured_messages_with_fallback_escalates_through_tier_ladder(monkeypatch):
    """
    Structured fallback should use the same tier ladder discipline as text calls.

    Why this matters:
    Provider fallback belongs in the provider abstraction, not routers or UI code.
    """

    provider = LiteLLMProvider()
    calls = []

    def fake_complete_structured_messages(*, messages, tier, response_model, max_tokens=2000):
        calls.append(tier)
        if tier == "flash":
            raise RuntimeError("flash structured call failed")

        return {
            "result": EstimationResult.model_validate(structured_payload()),
            "model": "deepseek-v4-pro",
            "tier": tier,
            "provider": "deepseek",
            "input_tokens": 10,
            "output_tokens": 20,
            "finish_reason": "stop",
            "timestamp": "2026-05-16T00:00:00+00:00",
        }

    monkeypatch.setattr(
        provider,
        "complete_structured_messages",
        fake_complete_structured_messages,
    )

    result = provider.complete_structured_messages_with_fallback(
        messages=[
            {"role": "system", "content": "Return structured estimate."},
            {"role": "user", "content": "Build onboarding SaaS."},
        ],
        starting_tier="flash",
        tier_ladder=["flash", "pro", "backup", "backup_pro"],
        response_model=EstimationResult,
    )

    assert calls == ["flash", "pro"]
    assert result["tier"] == "pro"
    assert result["fallback_used"] is True
    assert isinstance(result["result"], EstimationResult)


def test_complete_structured_messages_does_not_send_pydantic_model_class_to_litellm(monkeypatch):
    """
    Regression test for the real DeepSeek and Kimi runtime failure.

    Why this matters:
    Passing response_model=EstimationResult directly into litellm.completion made
    LiteLLM try to JSON serialize a Python ModelMetaclass. The real provider call
    then failed with "Object of type ModelMetaclass is not JSON serializable".

    The provider should enforce structured output locally:
    add JSON schema instructions to messages, receive text, parse JSON, and
    validate with Pydantic after the LiteLLM call.
    """

    provider = LiteLLMProvider()
    calls = {}

    def fake_completion(**kwargs):
        calls.update(kwargs)
        return FakeResponse(json.dumps(structured_payload()))

    monkeypatch.setattr("app.services.litellm_provider.litellm.completion", fake_completion)

    result = provider.complete_structured_messages(
        messages=[
            {"role": "system", "content": "You are an estimator."},
            {"role": "user", "content": "Build onboarding SaaS."},
        ],
        tier="flash",
        response_model=EstimationResult,
    )

    assert "response_model" not in calls
    assert "Return only valid JSON" in calls["messages"][0]["content"]
    assert "JSON schema" in calls["messages"][0]["content"]
    assert isinstance(result["result"], EstimationResult)


def test_complete_structured_messages_extracts_content_from_litellm_modelresponse_base_model(monkeypatch):
    """
    Regression test for real LiteLLM runtime behavior.

    Why this matters:
    LiteLLM ModelResponse is itself a Pydantic BaseModel. The provider must not
    treat every BaseModel response as the final structured payload. It should only
    accept an already parsed object when it is actually the requested response_model.
    Otherwise it must extract choices[0].message.content and validate that JSON.
    """

    from pydantic import BaseModel

    class ModelResponseLike(BaseModel):
        choices: list
        usage: object

    provider = LiteLLMProvider()

    def fake_completion(**kwargs):
        return ModelResponseLike(
            choices=[FakeChoice(json.dumps(structured_payload()))],
            usage=FakeUsage(),
        )

    monkeypatch.setattr("app.services.litellm_provider.litellm.completion", fake_completion)

    result = provider.complete_structured_messages(
        messages=[
            {"role": "system", "content": "You are an estimator."},
            {"role": "user", "content": "Build onboarding SaaS."},
        ],
        tier="flash",
        response_model=EstimationResult,
    )

    assert isinstance(result["result"], EstimationResult)
    assert result["result"].summary == "A structured estimate for a SaaS onboarding product."


def test_complete_structured_messages_normalizes_estimation_result_aggregate_totals(monkeypatch):
    """
    Provider JSON can be structurally useful but arithmetically inconsistent.

    Why this matters:
    Kimi has returned valid JSON where total_cost_eur did not equal the sum of
    phase cost_eur values. The model should estimate phases; deterministic
    aggregate totals should be computed by the backend before final Pydantic
    validation.
    """

    calls = {}

    payload = structured_payload()
    payload["total_cost_eur"] = 999999
    payload["total_duration_weeks"] = 999

    def fake_completion(**kwargs):
        calls.update(kwargs)
        return FakeResponse(json.dumps(payload))

    monkeypatch.setattr("app.services.litellm_provider.litellm.completion", fake_completion)

    provider = LiteLLMProvider()
    result = provider.complete_structured_messages(
        messages=[
            {"role": "system", "content": "Return only valid JSON."},
            {"role": "user", "content": "Build onboarding SaaS."},
        ],
        tier="backup",
        response_model=EstimationResult,
    )

    estimation = result["result"]

    assert estimation.total_cost_eur == sum(phase.cost_eur for phase in estimation.phases)
    assert estimation.total_duration_weeks == sum(phase.duration_weeks for phase in estimation.phases)
    assert result["provider"] == "kimi"
    assert calls["response_format"] == {"type": "json_object"}
