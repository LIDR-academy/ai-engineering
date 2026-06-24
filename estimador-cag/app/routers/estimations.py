"""
LAYER: routers (HTTP transport)
RESPONSIBILITY: Define estimation endpoints and wire HTTP requests to LLM services.
WHY IT EXISTS: Isolates FastAPI transport concerns from prompt building, caching,
               provider routing, and streaming business logic.
DEPENDS ON: fastapi, sse_starlette, app.schemas.estimation,
            app.services.llm_service, app.middleware.logging
"""

import json
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import ValidationError
from sse_starlette.sse import EventSourceResponse, ServerSentEvent

from app.guardrails.input import evaluate_input_guardrails
from app.middleware.logging import record_call_metrics
from app.schemas.estimation import (
    EstimateRequest,
    EstimateResponse,
    EstimationRequest,
    EstimationResponse,
)
from app.services.costs import estimate_cost_usd
from app.services.litellm_provider import LiteLLMProvider
from app.services.llm_service import (
    build_redis_cache,
    build_system_prompt,
    estimate,
    estimate_product,
    estimate_stream,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["estimations"])


def _normalize_estimation_response_payload(result: dict, prompt_version: str) -> dict:
    """Normalize stale stream-shaped cache payloads before FastAPI response validation."""

    if not isinstance(result, dict):
        return result

    if "text" not in result and "estimation" in result:
        return {
            "text": str(result["estimation"]),
            "prompt_version": str(result.get("prompt_version") or prompt_version),
        }

    if "prompt_version" not in result:
        normalized = dict(result)
        normalized["prompt_version"] = prompt_version
        return normalized

    return result


def _normalize_estimation_route_payload(result: dict, prompt_version: str) -> dict:
    """Normalize stale stream-shaped cached payloads before FastAPI validates the response."""

    if not isinstance(result, dict):
        return result

    normalized = dict(result)

    if "text" not in normalized and "estimation" in normalized:
        normalized["text"] = str(normalized["estimation"])

    normalized.setdefault("prompt_version", prompt_version)

    if normalized.get("input_tokens") is None:
        normalized["input_tokens"] = 0
    if normalized.get("output_tokens") is None:
        normalized["output_tokens"] = 0

    if "requested_tier" not in normalized and "tier" in normalized:
        normalized["requested_tier"] = normalized["tier"]
    if "served_tier" not in normalized and "tier" in normalized:
        normalized["served_tier"] = normalized["tier"]

    return normalized


@router.post(
    "/estimate",
    response_model=EstimateResponse | EstimationResponse,
    response_model_exclude_none=True,
)
async def create_estimation(
    request: Request,
    prompt_version: str = Query(default="v1", pattern=r"^v[0-9]+$"),
):
    """
    POST /api/v1/estimate

    Receives either the legacy transcription request or the Session 04 typed
    product request and returns the matching estimation response.
    """
    try:
        payload = await request.json()

        if {"description", "project_type", "detail_level", "output_format"}.issubset(payload):
            raw_description = payload.get("description")
            if isinstance(raw_description, str):
                guardrail_decision = evaluate_input_guardrails(raw_description)
                if not guardrail_decision.allowed:
                    logger.warning(
                        "blocked_typed_estimation_input reason_code=%s",
                        guardrail_decision.reason_code,
                    )
                    raise HTTPException(status_code=400, detail=guardrail_decision.to_detail())

            typed_request = EstimationRequest.model_validate(payload)
            result = estimate_product(typed_request, prompt_version=prompt_version)
            return _normalize_estimation_response_payload(result, prompt_version)

        legacy_request = EstimateRequest.model_validate(payload)
        result = estimate(
            legacy_request.transcription,
            tier=legacy_request.tier,
            history=legacy_request.history,
            max_history_turns=legacy_request.max_history_turns,
        )
        record_call_metrics(result)
        return _normalize_estimation_route_payload(result, prompt_version)
    except HTTPException as exc:
        raise exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Error LLM: {str(exc)}") from exc


@router.post("/estimate/stream")
def stream_estimation(request: EstimateRequest):
    """
    POST /api/v1/estimate/stream

    Streams an estimation using Server Sent Events.

    Event types:
    - token: partial text chunk
    - done: final metadata
    - error: failure details
    """

    def event_generator():
        started_at = datetime.now(UTC)
        output_chars = 0
        stream_chunks = 0
        full_response_parts: list[str] = []
        effective_tier = request.tier or "flash"

        try:
            system_prompt = build_system_prompt()
            provider = LiteLLMProvider()
            resolved = provider.resolve_model(effective_tier)
            cache = build_redis_cache()
            cache_key = cache.make_key(
                tier=effective_tier,
                model=resolved.model,
                system_prompt=system_prompt,
                transcription=request.transcription,
            )

            cached_result = cache.get(cache_key)
            if cached_result:
                cached_text = cached_result["estimation"]
                output_chars = len(cached_text)
                stream_chunks = 1
                yield ServerSentEvent(event="token", data=cached_text)

                finished_at = datetime.now(UTC)
                cached_cost = estimate_cost_usd(
                    model=cached_result.get("model", resolved.model),
                    input_tokens=cached_result.get("input_tokens"),
                    output_tokens=cached_result.get("output_tokens"),
                )
                record_call_metrics(
                    {
                        "endpoint": "/api/v1/estimate/stream",
                        "model": cached_result.get("model", resolved.model),
                        "tier": cached_result.get("tier", effective_tier),
                        "provider": cached_result.get("provider", resolved.provider),
                        "input_tokens": cached_result.get("input_tokens"),
                        "output_tokens": cached_result.get("output_tokens"),
                        "cost_usd": cached_result.get("cost_usd", cached_cost["cost_usd"]),
                        "cost_source": cached_result.get("cost_source", cached_cost["cost_source"]),
                        "pricing_model": cached_result.get("pricing_model", cached_cost["pricing_model"]),
                        "timestamp": cached_result.get("timestamp", finished_at.isoformat()),
                        "cached": True,
                        "cache_backend": cache.backend_name,
                        "stream_output_chars": output_chars,
                        "stream_chunks": stream_chunks,
                        "stream_cached": True,
                        "stream_started_at": started_at.isoformat(),
                        "stream_finished_at": finished_at.isoformat(),
                        "fallback_used": cached_result.get("fallback_used", False),
                        "finish_reason": cached_result.get("finish_reason", "stream_cached"),
                        "error_type": None,
                    }
                )
                metadata = {
                    "tier": effective_tier,
                    "output_chars": output_chars,
                    "started_at": started_at.isoformat(),
                    "finished_at": finished_at.isoformat(),
                    "cached": True,
                    "cache_backend": cache.backend_name,
                }
                yield ServerSentEvent(event="done", data=json.dumps(metadata))
                return

            for token in estimate_stream(
                request.transcription,
                tier=effective_tier,
                history=request.history,
                max_history_turns=request.max_history_turns,
            ):
                output_chars += len(token)
                stream_chunks += 1
                full_response_parts.append(token)
                yield ServerSentEvent(event="token", data=token)

            finished_at = datetime.now(UTC)
            full_response = "".join(full_response_parts)
            stream_cost = estimate_cost_usd(
                model=resolved.model,
                input_tokens=None,
                output_tokens=None,
            )
            cache_value = {
                "estimation": full_response,
                "model": resolved.model,
                "tier": effective_tier,
                "provider": resolved.provider,
                "input_tokens": None,
                "output_tokens": None,
                "cost_usd": stream_cost["cost_usd"],
                "cost_source": stream_cost["cost_source"],
                "pricing_model": stream_cost["pricing_model"],
                "timestamp": finished_at.isoformat(),
                "fallback_used": False,
                "finish_reason": "stream_done",
            }
            cache.set(cache_key, cache_value)

            metadata = {
                "tier": effective_tier,
                "output_chars": output_chars,
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat(),
                "cached": False,
                "cache_backend": cache.backend_name,
            }

            record_call_metrics(
                {
                    "endpoint": "/api/v1/estimate/stream",
                    "model": resolved.model,
                    "tier": effective_tier,
                    "provider": resolved.provider,
                    "input_tokens": None,
                    "output_tokens": None,
                    "cost_usd": stream_cost["cost_usd"],
                    "cost_source": stream_cost["cost_source"],
                    "pricing_model": stream_cost["pricing_model"],
                    "timestamp": finished_at.isoformat(),
                    "cached": False,
                    "cache_backend": cache.backend_name,
                    "stream_output_chars": output_chars,
                    "stream_chunks": stream_chunks,
                    "stream_cached": False,
                    "stream_started_at": started_at.isoformat(),
                    "stream_finished_at": finished_at.isoformat(),
                    "fallback_used": False,
                    "finish_reason": "stream_done",
                    "error_type": None,
                }
            )

            yield ServerSentEvent(event="done", data=json.dumps(metadata))

        except Exception as exc:
            yield ServerSentEvent(
                event="error",
                data=json.dumps({"detail": str(exc)}),
            )

    return EventSourceResponse(event_generator())
