from app.prompts.loader import render_estimation_prompt
from app.schemas.estimation import DetailLevel, EstimationRequest, OutputFormat, ProjectType


def _sample_request() -> EstimationRequest:
    return EstimationRequest(
        description="Build Atlas CRM onboarding with FastAPI and PostgreSQL.",
        project_type=ProjectType.WEB_SAAS,
        detail_level=DetailLevel.MEDIUM,
        output_format=OutputFormat.PHASES_TABLE,
    )


def test_v1_and_v2_prompts_force_raw_valid_json_for_structured_provider_path():
    request = _sample_request()

    for version in ("v1", "v2"):
        system_prompt, _user_prompt = render_estimation_prompt(request, version=version)
        lowered = system_prompt.lower()

        assert "valid json" in lowered
        assert "no markdown" in lowered
        assert "no prose" in lowered
        assert "no code fences" in lowered
