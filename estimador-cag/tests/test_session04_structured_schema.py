import pytest
from pydantic import ValidationError

from app.schemas.estimation import (
    DetailLevel,
    EstimationResponse,
    EstimationResult,
    OutputFormat,
    Phase,
    ProjectType,
)


def make_phase(
    *,
    name: str = "Discovery",
    duration_weeks: int = 2,
    cost_eur: int = 4000,
    confidence_pct: int = 80,
) -> Phase:
    """
    Test helper for one structured implementation phase.

    Why this matters:
    The UI should not need to parse markdown tables. A Phase gives the frontend
    stable fields for cards, tables, validation, cache rules, and metrics.
    """

    return Phase(
        name=name,
        summary="Clarify requirements and estimate delivery shape.",
        duration_weeks=duration_weeks,
        cost_eur=cost_eur,
        confidence_pct=confidence_pct,
        tasks=["Interview stakeholders", "Define scope", "Identify risks"],
        risks=["Unclear business rules"],
    )


def make_result(
    *,
    summary: str = "A structured estimate for a SaaS onboarding product.",
    total_duration_weeks: int = 4,
    total_cost_eur: int = 9000,
    confidence_pct: int = 75,
    phases: list[Phase] | None = None,
) -> EstimationResult:
    """
    Test helper for the full structured output.

    Why this matters:
    EstimationResult is the product contract. The model output becomes data,
    not just prose. That makes validation, rendering, and caching safer.

    Important:
    Only None means "use defaults". An empty list must stay empty so we can
    prove that Pydantic rejects empty phases.
    """

    if phases is None:
        phases = [
            make_phase(name="Discovery", duration_weeks=2, cost_eur=4000),
            make_phase(name="Build", duration_weeks=2, cost_eur=5000),
        ]

    return EstimationResult(
        summary=summary,
        project_type=ProjectType.WEB_SAAS,
        detail_level=DetailLevel.MEDIUM,
        output_format=OutputFormat.PHASES_TABLE,
        total_duration_weeks=total_duration_weeks,
        total_cost_eur=total_cost_eur,
        confidence_pct=confidence_pct,
        phases=phases,
        assumptions=["Email and password authentication only"],
        risks=["Reporting scope may grow"],
        recommendations=["Confirm approval workflow before build"],
    )


def test_phase_serializes_to_json_contract():
    """
    The frontend needs stable JSON fields for table rendering.
    This replaces fragile markdown parsing.
    """

    phase = make_phase()

    assert phase.model_dump(mode="json") == {
        "name": "Discovery",
        "summary": "Clarify requirements and estimate delivery shape.",
        "duration_weeks": 2,
        "cost_eur": 4000,
        "confidence_pct": 80,
        "tasks": ["Interview stakeholders", "Define scope", "Identify risks"],
        "risks": ["Unclear business rules"],
    }


def test_estimation_result_serializes_enum_values_for_frontend():
    """
    Enums must serialize as API friendly strings, not Python enum objects.
    This keeps Streamlit, curl, and future clients simple.
    """

    result = make_result()

    payload = result.model_dump(mode="json")

    assert payload["project_type"] == "web_saas"
    assert payload["detail_level"] == "medium"
    assert payload["output_format"] == "phases_table"
    assert payload["total_cost_eur"] == 9000
    assert len(payload["phases"]) == 2


def test_estimation_result_rejects_empty_phases():
    """
    A structured estimate without phases is not useful for a product UI.
    We reject it before it can be cached or rendered.
    """

    with pytest.raises(ValidationError):
        make_result(phases=[])


def test_estimation_result_rejects_phase_cost_mismatch():
    """
    The total must match the phase costs.

    Why this matters:
    This catches hallucinated arithmetic before the response reaches the user
    or the cache.
    """

    with pytest.raises(ValidationError):
        make_result(total_cost_eur=12345)


def test_estimation_result_rejects_invalid_confidence_values():
    """
    Confidence is a percentage. Values outside 0..100 are invalid model output.
    """

    with pytest.raises(ValidationError):
        make_phase(confidence_pct=101)

    with pytest.raises(ValidationError):
        make_result(confidence_pct=-1)


def test_low_confidence_result_requires_out_of_scope_summary():
    """
    Low confidence estimates must be visibly framed.

    Why this matters:
    If the model is uncertain, the user should not see a normal looking estimate
    pretending to be reliable.
    """

    with pytest.raises(ValidationError):
        make_result(
            summary="Maybe possible but unclear.",
            confidence_pct=40,
        )

    result = make_result(
        summary="Out of scope: requirements are too vague to estimate safely.",
        confidence_pct=40,
    )

    assert result.confidence_pct == 40


def test_structured_estimation_response_contains_result_and_prompt_version():
    """
    The response keeps prompt_version for traceability and adds result for
    structured rendering.

    text remains optional compatibility, but the product UI should prefer result.
    """

    result = make_result()

    response = EstimationResponse(
        result=result,
        text="Optional markdown compatibility text.",
        prompt_version="v2",
        cached=False,
        cache_backend="redis",
        model="deepseek-v4-flash",
        provider="deepseek",
        tier="flash",
    )

    payload = response.model_dump(mode="json")

    assert payload["result"]["summary"] == result.summary
    assert payload["prompt_version"] == "v2"
    assert payload["text"] == "Optional markdown compatibility text."
    assert payload["cached"] is False


def test_text_only_estimation_response_still_serializes_with_exclude_none():
    """
    Existing markdown clients should not be forced to receive structured fields.

    Why this matters:
    The structured contract is additive. Older Session 04 text callers can keep
    using exclude_none=True while the product UI migrates to result.
    """

    response = EstimationResponse(
        text="## Estimate\n\nThe implementation can be delivered in three phases.",
        prompt_version="v1",
    )

    assert response.model_dump(exclude_none=True) == {
        "text": "## Estimate\n\nThe implementation can be delivered in three phases.",
        "prompt_version": "v1",
    }
