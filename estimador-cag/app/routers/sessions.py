"""
LAYER: routers/session-memory
RESPONSIBILITY: Expose Session 05 conversational estimation endpoints.
WHY IT EXISTS: Keeps multipart session flow separate from the legacy /api/v1
               estimator route while reusing the same service layer.
"""

from __future__ import annotations

import json
import time
from typing import Annotated, Literal

import structlog
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import ValidationError

from app.config import settings
from app.guardrails.input import evaluate_input_guardrails
from app.schemas.estimation import (
    DetailLevel,
    EstimationRequest,
    OutputFormat,
    ProjectType,
    TurnObservation,
)
from app.services.attachments import (
    AttachmentExtractionError,
    extract_upload_text,
    format_attachments_for_prompt,
)
from app.services.llm_service import estimate_product
from app.services.sessions import global_session_store

router = APIRouter(tags=["sessions"])
TierName = Literal["flash", "pro", "backup", "backup_pro"]
logger = structlog.get_logger(__name__)


def _assistant_content_for_model_history(result: dict) -> str:
    """Return assistant history in model friendly structured form, not UI Markdown."""

    structured_result = result.get("result")
    if hasattr(structured_result, "model_dump_json"):
        return structured_result.model_dump_json()

    if isinstance(structured_result, dict):
        return json.dumps(structured_result, ensure_ascii=False)

    return str(result.get("text") or "")



def _fake_structured_result(
    request: EstimationRequest,
    transcript: str,
    attachments_text: str,
    conversation_history: list[dict[str, str]] | None = None,
) -> dict:
    """Return deterministic structured output for stress smoke runs only."""

    history_text = json.dumps(conversation_history or [], ensure_ascii=False)
    seed_text = f"{transcript}\n{attachments_text}"
    context_text = f"{history_text}\n{seed_text}"
    token_estimate_in = max(1, len(context_text) // 4)
    token_estimate_out = 220
    base_cost = round((token_estimate_in * 0.00000007) + (token_estimate_out * 0.00000028), 8)
    return {
        "summary": f"Deterministic stress estimate for {request.project_type.value}. {seed_text[:220]}",
        "project_type": request.project_type.value,
        "detail_level": request.detail_level.value,
        "output_format": request.output_format.value,
        "total_duration_weeks": 6.0,
        "total_cost_eur": 30000,
        "confidence_pct": 75,
        "phases": [
            {
                "name": "Discovery and scope control",
                "summary": "Clarify requirements, risks, and acceptance criteria.",
                "duration_weeks": 2.0,
                "cost_eur": 10000,
                "confidence_pct": 80,
                "tasks": ["Review transcript", "Review attachments", "Define backlog"],
                "risks": ["Synthetic stress mode does not represent live LLM quality"],
            },
            {
                "name": "Implementation baseline",
                "summary": "Build the first shippable version with observability.",
                "duration_weeks": 4.0,
                "cost_eur": 20000,
                "confidence_pct": 70,
                "tasks": ["Implement core flow", "Add tests", "Prepare release report"],
                "risks": ["Scope may grow across later turns"],
            },
        ],
        "assumptions": ["Stress fake provider is enabled", "Numbers are deterministic smoke values"],
        "risks": ["Use live provider for final production-grade cost and latency curves"],
        "recommendations": ["Compare deterministic smoke with one live run before the session"],
        "_meta": {
            "input_tokens": token_estimate_in,
            "output_tokens": token_estimate_out,
            "cost_usd": base_cost,
        },
    }


def _fake_estimate_product(
    request: EstimationRequest,
    *,
    transcript: str,
    attachments_text: str,
    tier: TierName | None,
    prompt_version: str,
    conversation_history: list[dict[str, str]] | None = None,
) -> dict:
    """Session 06 stress-only fake provider preserving the HTTP response contract."""

    structured_result = _fake_structured_result(
        request,
        transcript,
        attachments_text,
        conversation_history=conversation_history,
    )
    meta = structured_result.pop("_meta")
    served_tier = tier or request.tier or "stress_fake"
    return {
        "prompt_version": prompt_version,
        "result": structured_result,
        "text": structured_result["summary"],
        "cached": False,
        "cache_backend": "stress_fake",
        "model": "stress-fake-local",
        "provider": "deterministic-local",
        "tier": served_tier,
        "requested_tier": served_tier,
        "served_tier": served_tier,
        "fallback_used": False,
        "input_tokens": meta["input_tokens"],
        "output_tokens": meta["output_tokens"],
        "cost_usd": meta["cost_usd"],
        "semantic_cache_mode": "off",
        "semantic_candidate_found": False,
    }


def _cache_hit_kind(result: dict) -> Literal["none", "exact", "semantic"]:
    """Normalize cache metadata into the Session 06 allowed vocabulary."""

    if result.get("cached") is True:
        return "exact"
    if result.get("semantic_cache_hit") is True or result.get("cache_backend") == "semantic":
        return "semantic"
    return "none"


def _numeric_int(value: object, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def _numeric_float(value: object, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return default


@router.post("/sessions")
def create_session() -> dict[str, str]:
    """Create an empty volatile in process estimation session."""

    session = global_session_store.create_session()
    return {"session_id": session.session_id}


@router.get("/sessions/{session_id}")
def read_session(session_id: str) -> dict:
    """Return lightweight session diagnostics for the Streamlit metadata panel."""

    try:
        session = global_session_store.require_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown session_id") from exc

    return {
        "session_id": session.session_id,
        "project_metadata": session.project_metadata.model_dump(mode="json"),
        "history_turns": session.history.turn_count,
        "total_turn_count": session.total_turn_count,
        "max_history_turns": session.history.max_turns,
        "message_count": len(session.history.to_messages_list(system_prompt="")),
        "messages_in_window": len(session.history.to_messages_list(system_prompt="")),
        "anchors_count": 0,
        "summary_chars": 0,
        "last_resolved_tier": (session.last_turn_observed or {}).get("last_resolved_tier", "default"),
        "last_tier_rule": "not_implemented_in_mandatory_session06",
        "last_turn_observed": session.last_turn_observed,
    }


@router.post("/sessions/{session_id}/estimate")
async def estimate_session(
    session_id: str,
    transcript: Annotated[str, Form(min_length=20)],
    project_type: Annotated[ProjectType, Form()] = ProjectType.WEB_SAAS,
    detail_level: Annotated[DetailLevel, Form()] = DetailLevel.MEDIUM,
    output_format: Annotated[OutputFormat, Form()] = OutputFormat.PHASES_TABLE,
    tier: Annotated[TierName | None, Form()] = None,
    prompt_version: Annotated[str, Form(pattern=r"^v[0-9]+$")] = "v1",
    attachments: Annotated[list[UploadFile] | None, File()] = None,
) -> dict:
    """Estimate one turn in a session using multipart transcript plus attachments."""

    started_at = time.perf_counter()

    try:
        session = global_session_store.require_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown session_id") from exc

    guardrail_decision = evaluate_input_guardrails(transcript)
    if not guardrail_decision.allowed:
        raise HTTPException(status_code=400, detail=guardrail_decision.to_detail())

    extracted_attachments = []
    for upload in attachments or []:
        try:
            extracted_attachments.append(await extract_upload_text(upload))
        except AttachmentExtractionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    attachments_text = format_attachments_for_prompt(extracted_attachments)
    attachment_names = [attachment.filename for attachment in extracted_attachments]

    try:
        request = EstimationRequest(
            description=transcript,
            project_type=project_type,
            detail_level=detail_level,
            output_format=output_format,
            tier=tier,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    conversation_history = session.history.to_messages_list(system_prompt="")[1:]

    try:
        if settings.stress_fake_provider:
            result = _fake_estimate_product(
                request,
                transcript=transcript,
                attachments_text=attachments_text,
                tier=tier,
                prompt_version=prompt_version,
                conversation_history=conversation_history,
            )
        else:
            result = estimate_product(
                request,
                tier=tier,
                prompt_version=prompt_version,
                project_metadata=session.project_metadata,
                attachments_text=attachments_text,
                conversation_history=conversation_history,
            )
    except TimeoutError as exc:
        raise HTTPException(status_code=502, detail=f"Provider timed out: {exc}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=f"Provider failed: {exc}") from exc

    assistant_text = result.get("text") or ""
    assistant_history_content = _assistant_content_for_model_history(result)
    session.add_turn(user_content=transcript, assistant_content=assistant_history_content)
    session.update_metadata(
        transcript=f"{transcript}\n\n{attachments_text}",
        assistant_text=assistant_text,
        attachment_names=attachment_names,
    )

    result["session_id"] = session.session_id
    result["project_metadata"] = session.project_metadata.model_dump(mode="json")
    result["history_turns"] = session.history.turn_count
    result["total_turn_count"] = session.total_turn_count
    result["max_history_turns"] = session.history.max_turns
    result["attachments_processed"] = attachment_names

    route_latency_ms = int((time.perf_counter() - started_at) * 1000)
    attachments_total_chars = sum(len(attachment.text) for attachment in extracted_attachments)
    enriched_transcript_chars = len(transcript) + len(attachments_text)
    observation = TurnObservation(
        turn_index=session.total_turn_count,
        session_id=session.session_id,
        enriched_transcript_chars=enriched_transcript_chars,
        attachments_total_chars=attachments_total_chars,
        messages_in_window=len(session.history.to_messages_list(system_prompt="")),
        anchors_count=0,
        summary_chars=0,
        tokens_in=_numeric_int(result.get("input_tokens") or result.get("tokens_in")),
        tokens_out=_numeric_int(result.get("output_tokens") or result.get("tokens_out")),
        cost_usd=_numeric_float(result.get("cost_usd")),
        latency_ms=_numeric_int(result.get("latency_ms"), route_latency_ms),
        cache_hit_kind=_cache_hit_kind(result),
        last_resolved_tier=str(result.get("served_tier") or result.get("tier") or "default"),
    )
    observation_payload = observation.model_dump(mode="json")
    session.last_turn_observed = observation_payload
    logger.info("turn_observed", **observation_payload)
    result["turn_observed"] = observation_payload
    return result
