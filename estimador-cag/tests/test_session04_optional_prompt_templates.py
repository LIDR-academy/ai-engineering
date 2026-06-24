import pytest
from jinja2 import TemplateNotFound

from app.prompts import loader
from app.prompts.loader import render_estimation_prompt
from app.schemas.estimation import (
    DetailLevel,
    EstimationRequest,
    OutputFormat,
    ProjectType,
    ReferenceProject,
)

DESCRIPTION = (
    "Build a partner onboarding SaaS with account approval, role based review, "
    "email notifications, and operational reporting for support managers."
)


def make_request(reference_projects=None) -> EstimationRequest:
    return EstimationRequest(
        description=DESCRIPTION,
        project_type=ProjectType.WEB_SAAS,
        detail_level=DetailLevel.DETAILED,
        output_format=OutputFormat.PHASES_TABLE,
        reference_projects=reference_projects,
    )


def test_reference_project_schema_serializes_optional_context():
    request = make_request(
        reference_projects=[
            ReferenceProject(
                name="CRM migration",
                summary="Moved spreadsheet workflows to a role based SaaS.",
                estimated_hours=260,
                notes="Permissions and reporting were the main risks.",
            )
        ]
    )

    payload = request.model_dump(mode="json", exclude_none=True)

    assert payload["reference_projects"] == [
        {
            "name": "CRM migration",
            "summary": "Moved spreadsheet workflows to a role based SaaS.",
            "estimated_hours": 260,
            "notes": "Permissions and reporting were the main risks.",
        }
    ]


def test_v2_prompt_version_renders_distinct_system_prompt():
    request = make_request()

    v1_system, _ = render_estimation_prompt(request, version="v1")
    v2_system, _ = render_estimation_prompt(request, version="v2")

    assert "Prompt version: v1" in v1_system
    assert "Prompt version: v2" in v2_system
    assert v1_system != v2_system
    assert "review-ready estimate" in v2_system


def test_unknown_prompt_version_fails_fast():
    with pytest.raises(TemplateNotFound):
        render_estimation_prompt(make_request(), version="v999")


def test_reference_projects_render_when_present_and_do_not_render_when_absent():
    reference_project = ReferenceProject(
        name="Internal CRM migration",
        summary="Migrated sales workflows from spreadsheets to a role based SaaS.",
        estimated_hours=260,
        notes="Reporting and permissions were the largest risks.",
    )

    system_with_refs, _ = render_estimation_prompt(
        make_request(reference_projects=[reference_project]),
        version="v1",
    )
    system_without_refs, _ = render_estimation_prompt(make_request(), version="v1")

    assert "Similar reference projects supplied by the user" in system_with_refs
    assert "Internal CRM migration" in system_with_refs
    assert "260" in system_with_refs
    assert "Similar reference projects supplied by the user" not in system_without_refs


def test_prompt_loader_logs_version_and_hash(monkeypatch):
    events = []

    class FakeLogger:
        def info(self, event_name, **kwargs):
            events.append((event_name, kwargs))

    monkeypatch.setattr(loader, "logger", FakeLogger())

    render_estimation_prompt(make_request(), version="v1")

    assert events
    event_name, payload = events[0]
    assert event_name == "prompt_rendered"
    assert payload["prompt_version"] == "v1"
    assert len(payload["prompt_hash"]) == 64
    assert payload["system_chars"] > 0
    assert payload["user_chars"] > 0
