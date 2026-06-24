from app.prompts.loader import render_estimation_prompt
from app.schemas.estimation import DetailLevel, EstimationRequest, OutputFormat, ProjectType
from app.services.llm_service import _build_structured_product_system_prompt
from app.services.sessions import ProjectMetadata


def make_request():
    return EstimationRequest(
        description="Build Atlas CRM with approval workflows and reporting dashboards.",
        project_type=ProjectType.WEB_SAAS,
        detail_level=DetailLevel.MEDIUM,
        output_format=OutputFormat.PHASES_TABLE,
    )


def test_prompt_templates_include_project_metadata_and_attachments_blocks():
    metadata = ProjectMetadata(project_name="Atlas CRM", mentioned_technologies=["FastAPI"])
    system, user = render_estimation_prompt(
        make_request(),
        version="v2",
        project_metadata=metadata,
        attachments_text="--- attachment: spec.pdf ---\nUse PostgreSQL.\n--- end attachment: spec.pdf ---",
    )
    assert "<project_metadata>" in system
    assert "project_name: Atlas CRM" in system
    assert "mentioned_technologies: FastAPI" in system
    assert "<attachments>" in user
    assert "--- attachment: spec.pdf ---" in user
    assert "Use PostgreSQL." in user


def test_structured_system_prompt_injects_project_metadata_for_actual_llm_call():
    metadata = ProjectMetadata(project_name="Atlas CRM", mentioned_technologies=["FastAPI"])
    system = _build_structured_product_system_prompt("v2", project_metadata=metadata)
    assert "<project_metadata>" in system
    assert "project_name: Atlas CRM" in system
    assert "FastAPI" in system
