import pytest
from jinja2 import StrictUndefined, UndefinedError

from app.prompts.loader import _build_environment, render_estimation_prompt
from app.schemas.estimation import (
    DetailLevel,
    EstimationRequest,
    OutputFormat,
    ProjectType,
)

DESCRIPTION = (
    "Build a B2B onboarding platform with account approval, role-based admin review, "
    "email notifications, and a reporting dashboard for operations managers."
)


def make_request(
    *,
    output_format: OutputFormat = OutputFormat.PHASES_TABLE,
    detail_level: DetailLevel = DetailLevel.MEDIUM,
) -> EstimationRequest:
    return EstimationRequest(
        description=DESCRIPTION,
        project_type=ProjectType.WEB_SAAS,
        detail_level=detail_level,
        output_format=output_format,
    )


def test_rendered_user_prompt_wraps_exact_description_in_project_description_block():
    _, user = render_estimation_prompt(make_request())

    assert "<project_description>" in user
    assert DESCRIPTION in user
    assert "</project_description>" in user


def test_phases_table_system_mentions_confidence_pct_but_narrative_does_not():
    phases_system, _ = render_estimation_prompt(
        make_request(output_format=OutputFormat.PHASES_TABLE)
    )
    narrative_system, _ = render_estimation_prompt(
        make_request(output_format=OutputFormat.NARRATIVE)
    )

    assert "confidence_pct" in phases_system
    assert "confidence_pct" not in narrative_system


def test_detailed_system_requests_assumptions_per_phase_but_summary_does_not():
    detailed_system, _ = render_estimation_prompt(
        make_request(detail_level=DetailLevel.DETAILED)
    )
    summary_system, _ = render_estimation_prompt(
        make_request(detail_level=DetailLevel.SUMMARY)
    )

    assert "List assumptions per phase" in detailed_system
    assert "List assumptions per phase" not in summary_system


def test_prompt_environment_uses_strict_undefined():
    environment = _build_environment()

    assert environment.undefined is StrictUndefined

    with pytest.raises(UndefinedError):
        environment.from_string("{{ misspelled_variable }}").render({})
