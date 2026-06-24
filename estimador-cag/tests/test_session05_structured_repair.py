import json

from app.schemas.estimation import EstimationResult
from app.services.litellm_provider import LiteLLMProvider


def structured_payload() -> dict:
    return {
        "summary": "Atlas CRM reporting extension estimate.",
        "project_type": "internal_tool",
        "detail_level": "summary",
        "output_format": "narrative",
        "total_duration_weeks": 1.5,
        "total_cost_eur": 4000,
        "confidence_pct": 75,
        "phases": [
            {
                "name": "Reporting dashboards",
                "summary": "Add operational dashboards and access rules.",
                "duration_weeks": 1.5,
                "cost_eur": 4000,
                "confidence_pct": 75,
                "tasks": ["Define dashboard scope", "Build views", "QA permissions"],
                "risks": ["Reporting scope may expand."],
            }
        ],
        "assumptions": ["Existing authentication remains in scope."],
        "risks": ["Dashboard requirements may grow."],
        "recommendations": ["Confirm role matrix before implementation."],
    }


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeChoice:
    def __init__(self, content, finish_reason="stop"):
        self.message = FakeMessage(content)
        self.finish_reason = finish_reason


class FakeUsage:
    prompt_tokens = 10
    completion_tokens = 20


class FakeResponse:
    def __init__(self, content):
        self.choices = [FakeChoice(content)]
        self.usage = FakeUsage()


def test_structured_provider_repairs_markdown_response_into_valid_schema(monkeypatch):
    provider = LiteLLMProvider()
    calls = []

    def fake_completion(**kwargs):
        calls.append(kwargs)

        if len(calls) == 1:
            return FakeResponse(
                "## Product estimate\n\n"
                "Add reporting dashboards for Atlas CRM. Estimated duration: 1.5 weeks."
            )

        return FakeResponse(json.dumps(structured_payload()))

    monkeypatch.setattr("app.services.litellm_provider.litellm.completion", fake_completion)

    result = provider.complete_structured_messages(
        messages=[
            {"role": "system", "content": "Return only valid JSON."},
            {"role": "user", "content": "Estimate Atlas CRM reporting dashboards."},
        ],
        tier="flash",
        response_model=EstimationResult,
    )

    assert len(calls) == 2
    assert result["result"].summary == "Atlas CRM reporting extension estimate."
    assert result["result"].total_duration_weeks == 1.5

    repair_messages = calls[1]["messages"]
    repair_text = "\n".join(message["content"] for message in repair_messages)

    assert "repair" in repair_text.lower()
    assert "JSON schema" in repair_text
    assert "Product estimate" in repair_text
    assert calls[1]["response_format"] == {"type": "json_object"}


def test_structured_provider_repairs_schema_invalid_json_response(monkeypatch):
    provider = LiteLLMProvider()
    calls = []

    invalid_payload = structured_payload()
    invalid_payload["phases"] = []

    def fake_completion(**kwargs):
        calls.append(kwargs)

        if len(calls) == 1:
            return FakeResponse(json.dumps(invalid_payload))

        return FakeResponse(json.dumps(structured_payload()))

    monkeypatch.setattr("app.services.litellm_provider.litellm.completion", fake_completion)

    result = provider.complete_structured_messages(
        messages=[
            {"role": "system", "content": "Return only valid JSON."},
            {"role": "user", "content": "Estimate Atlas CRM reporting dashboards."},
        ],
        tier="flash",
        response_model=EstimationResult,
    )

    assert len(calls) == 2
    assert isinstance(result["result"], EstimationResult)
    assert result["result"].phases
