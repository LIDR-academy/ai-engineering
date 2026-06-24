from app.schemas.estimation import (
    DetailLevel,
    EstimationResult,
    OutputFormat,
    ProjectType,
)
from app.services.llm_service import _build_structured_product_system_prompt


def test_structured_system_prompt_uses_schema_enum_values_only():
    prompt = _build_structured_product_system_prompt("v1")

    for value in ProjectType:
        assert value.value in prompt

    for value in DetailLevel:
        assert value.value in prompt

    for value in OutputFormat:
        assert value.value in prompt

    assert "automation" not in prompt
    assert "data_ai" not in prompt


def test_estimation_result_accepts_fractional_duration_weeks_from_live_models():
    payload = {
        "summary": "Atlas CRM onboarding estimate.",
        "project_type": "internal_tool",
        "detail_level": "summary",
        "output_format": "narrative",
        "total_duration_weeks": 1.5,
        "total_cost_eur": 4000,
        "confidence_pct": 70,
        "phases": [
            {
                "name": "Reporting dashboards",
                "summary": "Add operational reporting dashboards.",
                "duration_weeks": 1.5,
                "cost_eur": 4000,
                "confidence_pct": 70,
                "tasks": ["Dashboard views", "Permissions", "QA"],
                "risks": ["Reporting scope may expand."],
            }
        ],
        "assumptions": ["Existing authentication remains in scope."],
        "risks": ["Third party requirements may expand."],
        "recommendations": ["Confirm dashboard roles before implementation."],
    }

    result = EstimationResult.model_validate(payload)

    assert result.phases[0].duration_weeks == 1.5
    assert result.total_duration_weeks == 1.5
