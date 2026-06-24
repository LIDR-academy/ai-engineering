"""
LAYER: prompt rendering
RESPONSIBILITY: Render versioned estimation prompts from typed request objects.
WHY IT EXISTS: Keeps product prompt text out of routers and provider code while
               making prompt versions testable and reviewable.
"""

import hashlib
from pathlib import Path

import structlog
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from app.schemas.estimation import EstimationRequest

PROMPT_ROOT = Path(__file__).resolve().parent
logger = structlog.get_logger(__name__)


def _build_environment() -> Environment:
    """Build the Jinja2 environment used by all versioned prompt templates."""

    return Environment(
        loader=FileSystemLoader(PROMPT_ROOT),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=select_autoescape(default=False),
    )


def render_estimation_prompt(
    request: EstimationRequest,
    version: str = "v1",
    project_metadata: object | None = None,
    attachments_text: str | None = None,
) -> tuple[str, str]:
    """
    Render the system and user prompts for a typed estimation request.

    Args:
        request: Validated product estimation request.
        version: Prompt version directory under app/prompts/estimation/.

    Returns:
        A tuple of rendered system and user prompt strings.
    """

    environment = _build_environment()
    template_prefix = f"estimation/{version}"

    context = request.model_dump(mode="json")
    context["prompt_version"] = version
    if hasattr(project_metadata, "to_prompt_block"):
        context["project_metadata"] = project_metadata.to_prompt_block()
    elif isinstance(project_metadata, dict):
        context["project_metadata"] = "\n".join(
            f"{key}: {value}" for key, value in project_metadata.items() if value not in (None, [], "")
        )
    else:
        context["project_metadata"] = ""
    context["attachments_text"] = attachments_text or ""

    system_template = environment.get_template(f"{template_prefix}/system.j2")
    user_template = environment.get_template(f"{template_prefix}/user.j2")

    system = system_template.render(**context).strip()
    user = user_template.render(**context).strip()
    prompt_hash = hashlib.sha256(f"{system}\n\n{user}".encode()).hexdigest()

    logger.info(
        "prompt_rendered",
        prompt_version=version,
        prompt_hash=prompt_hash,
        system_chars=len(system),
        user_chars=len(user),
    )

    return system, user
