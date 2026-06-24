"""
LAYER: services (business logic)
RESPONSIBILITY: Build system prompts, execute LLM calls with tier routing, and parse responses
WHY IT EXISTS: Separates prompt engineering and LLM communication from HTTP transport.
DEPENDS ON: app.config (Settings, tier routing), app.context.examples (CAG data)
"""

import json
import logging

from redis import Redis

from app.config import TierName, settings
from app.context.examples import ESTIMATION_EXAMPLES
from app.guardrails.output import evaluate_output_guardrails
from app.prompts.loader import render_estimation_prompt
from app.schemas.estimation import EstimationRequest, EstimationResult
from app.services.cache import RedisEstimationCache
from app.services.conversation import ConversationTurn
from app.services.litellm_provider import LiteLLMProvider
from app.services.semantic_cache import build_semantic_bucket, get_global_semantic_shadow_cache

logger = logging.getLogger(__name__)


def _get_provider(tier: str) -> str:
    """Deriva el nombre del proveedor a partir del tier."""
    if tier in ("flash", "pro"):
        return "deepseek"
    elif tier in ("backup", "backup_pro"):
        return "kimi"
    return "unknown"

def _temperature_for_model(model: str) -> float:
    """
    Return provider-safe temperature.

    Kimi K2 models reject arbitrary temperature values and require 1.
    DeepSeek accepts lower deterministic values such as 0.3.
    """
    if model.startswith("kimi-k2."):
        return 1.0
    return 0.3


def build_system_prompt() -> str:
    """Constructs the CAG system prompt with few-shot examples."""
    examples_text = "\n\n---\n\n".join(
        f"TRANSCRIPCION:\n{ex['meeting_summary']}\n\nESTIMACION GENERADA:\n{ex['estimation']}"
        for ex in ESTIMATION_EXAMPLES
    )
    return f"""Eres un estimador de software senior con 15 anos de experiencia.
Generas estimaciones detalladas basandote en transcripciones de reuniones.

Reglas:
- Desglosa en tareas concretas (horas por tarea)
- Incluye total de horas, equipo recomendado y duracion estimada
- Se realista, no optimista
- Usa markdown para la estimacion

Ejemplos de referencia:

{examples_text}"""



def build_redis_cache() -> RedisEstimationCache:
    """
    Build the Redis exact response cache from application settings.

    LAYER: services
    RESPONSIBILITY: Create the process-independent cache backend used by estimate().
    WHY IT EXISTS: Keeps Redis client construction out of endpoint code and makes
                   cache wiring testable.
    DEPENDS ON: settings.redis_url, settings.cache_ttl_seconds, redis.Redis.
    """
    redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    return RedisEstimationCache(
        redis_client=redis_client,
        ttl_seconds=settings.cache_ttl_seconds,
    )

def estimate_with_exact_cache(
    *,
    transcription: str,
    tier: str,
    model: str,
    system_prompt: str,
    cache,
    model_call,
) -> dict:
    """
    Orchestrate exact response caching around an LLM estimation call.

    LAYER: services
    RESPONSIBILITY: Check exact cache before calling the model and store fresh responses.
    WHY IT EXISTS: Keeps cache orchestration testable without making real provider calls.
    DEPENDS ON: cache object with make_key/get/set/backend_name and a zero-arg model_call.
    """
    cache_key = cache.make_key(
        tier=tier,
        model=model,
        system_prompt=system_prompt,
        transcription=transcription,
    )

    cached_result = cache.get(cache_key)
    if cached_result is not None:
        result = cached_result.copy()
        result["cached"] = True
        result["cache_backend"] = cache.backend_name
        return result

    result = model_call().copy()
    result["cached"] = False
    result["cache_backend"] = cache.backend_name
    cache.set(cache_key, result.copy())
    return result

def estimate(
    transcription: str,
    tier: TierName | None = None,
    history: list[ConversationTurn] | None = None,
    max_history_turns: int = 6,
) -> dict:
    """
    Synchronous LLM call with Redis exact cache and LiteLLM provider fallback.

    LAYER: services
    RESPONSIBILITY: Orchestrate CAG prompt creation, Redis exact cache, LiteLLM call,
                    fallback routing, and normalized response metadata.
    WHY IT EXISTS: Keeps HTTP routers thin while centralizing the application use case.
    DEPENDS ON: build_system_prompt, build_redis_cache, LiteLLMProvider.
    """
    system_prompt = build_system_prompt()
    effective_tier = tier or settings.llm_tier
    provider = LiteLLMProvider()
    resolved = provider.resolve_model(effective_tier)
    cache = build_redis_cache()

    def model_call() -> dict:
        logger.info(f"Calling LiteLLM starting_tier={effective_tier}, model={resolved.model}")
        return provider.complete_with_fallback(
            transcription=transcription,
            system_prompt=system_prompt,
            starting_tier=effective_tier,
            tier_ladder=settings.tier_ladder,
            max_tokens=2000,
            history=history,
            max_history_turns=max_history_turns,
        )

    return estimate_with_exact_cache(
        transcription=transcription,
        tier=effective_tier,
        model=resolved.model,
        system_prompt=system_prompt,
        cache=cache,
        model_call=model_call,
    )



def _build_structured_product_system_prompt(prompt_version: str, project_metadata: object | None = None) -> str:
    """
    Build the system prompt for structured product estimates.

    The human-readable v1/v2 templates may discuss presentation style.
    The provider path must stay schema-first and JSON-only.
    """

    from app.schemas.estimation import DetailLevel, OutputFormat, ProjectType

    if hasattr(project_metadata, "to_prompt_block"):
        metadata_block = project_metadata.to_prompt_block()
    elif isinstance(project_metadata, dict):
        metadata_block = "\n".join(
            f"{key}: {value}" for key, value in project_metadata.items() if value not in (None, [], "")
        )
    else:
        metadata_block = ""

    project_type_values = ", ".join(value.value for value in ProjectType)
    detail_level_values = ", ".join(value.value for value in DetailLevel)
    output_format_values = ", ".join(value.value for value in OutputFormat)

    return (
        "You are a senior software estimation engine. "
        f"Prompt version: {prompt_version}. "
        "Return only valid JSON. Return exactly one JSON object. "
        "Do not use headings, bullets, prose tables, or display formatting. "
        "Do not use code fences. "
        "Do not add prose before or after the JSON. "
        "Return a single JSON object compatible with EstimationResult. "
        "Use these enum values exactly: "
        f"project_type must be one of {project_type_values}; "
        f"detail_level must be one of {detail_level_values}; "
        f"output_format must be one of {output_format_values}. "
        "Each phase must include name, summary, duration_weeks, cost_eur, "
        "confidence_pct, tasks, and risks. "
        "duration_weeks and total_duration_weeks may be whole numbers or decimals, for example 1, 1.5, or 2. "
        "cost_eur and total_cost_eur must be integers. "
        "Make total_cost_eur equal the sum of all phase cost_eur values. "
        "Make total_duration_weeks no smaller than the longest phase and no larger "
        "than the sum of phase duration_weeks values. "
        "If confidence_pct is below 50, summary must start with 'Out of scope:'. "
        "Use project_metadata as stable context across turns without inventing missing facts. "
        f"<project_metadata>\n{metadata_block}\n</project_metadata>"
    )


def _estimation_result_to_text(result: EstimationResult) -> str:
    """
    Render structured estimation data into a small markdown compatibility text.

    LAYER: services
    RESPONSIBILITY: Preserve old text consumers while the product UI moves to fields.
    WHY IT EXISTS: Session 04 should be additive. Structured result is primary,
                   text is compatibility.
    """

    phase_lines = [
        f"- {phase.name}: {phase.duration_weeks} weeks, {phase.cost_eur} EUR"
        for phase in result.phases
    ]
    assumptions = "\n".join(f"- {item}" for item in result.assumptions) or "- None"
    risks = "\n".join(f"- {item}" for item in result.risks) or "- None"
    recommendations = "\n".join(f"- {item}" for item in result.recommendations) or "- None"

    return (
        f"## Product estimate\n\n"
        f"{result.summary}\n\n"
        f"Total duration: {result.total_duration_weeks} weeks\n\n"
        f"Total cost: {result.total_cost_eur} EUR\n\n"
        f"Confidence: {result.confidence_pct}%\n\n"
        f"### Phases\n"
        f"{chr(10).join(phase_lines)}\n\n"
        f"### Assumptions\n"
        f"{assumptions}\n\n"
        f"### Risks\n"
        f"{risks}\n\n"
        f"### Recommendations\n"
        f"{recommendations}"
    )


def build_semantic_shadow_cache():
    """
    Return the semantic shadow cache implementation.

    Kept as a small factory so tests can monkeypatch semantic cache behavior
    without touching global process state.
    """

    return get_global_semantic_shadow_cache()


def _semantic_shadow_disabled_metadata(mode: str) -> dict:
    """Return explicit metadata when semantic cache is off or skipped."""

    return {
        "semantic_cache_mode": mode,
        "semantic_candidate_found": False,
        "semantic_candidate_key": None,
        "semantic_similarity": None,
        "semantic_bucket": None,
    }


def estimate_product(
    request: EstimationRequest,
    tier: TierName | None = None,
    prompt_version: str = "v1",
    project_metadata: object | None = None,
    attachments_text: str | None = None,
    conversation_history: list[dict[str, str]] | None = None,
) -> dict:
    """
    Estimate a typed product request using structured output.

    LAYER: services
    RESPONSIBILITY: Render Session 04 prompts, call the structured provider path,
                    validate EstimationResult, exact-cache only valid responses,
                    and return a field based EstimationResponse shape.
    WHY IT EXISTS: The product frontend should render data fields instead of
                   parsing markdown.
    DEPENDS ON: render_estimation_prompt, Redis exact cache, LiteLLMProvider.
    """
    render_kwargs: dict[str, object] = {"version": prompt_version}
    if project_metadata is not None:
        render_kwargs["project_metadata"] = project_metadata
    if attachments_text:
        render_kwargs["attachments_text"] = attachments_text

    template_system_prompt, user_prompt = render_estimation_prompt(request, **render_kwargs)
    system_prompt = _build_structured_product_system_prompt(
        prompt_version,
        project_metadata=project_metadata,
    )
    history_messages = conversation_history or []
    messages = [
        {"role": "system", "content": system_prompt},
        *history_messages,
        {"role": "user", "content": user_prompt},
    ]

    effective_tier = tier or request.tier or settings.llm_tier
    provider = LiteLLMProvider()
    resolved = provider.resolve_model(effective_tier)
    cache = build_redis_cache()

    if project_metadata is None and not attachments_text and not conversation_history:
        cache_identity = request.model_dump_json()
    else:
        cache_identity = json.dumps(
            {
                "request": request.model_dump(mode="json"),
                "prompt_version": prompt_version,
                "requested_tier": effective_tier,
                "project_metadata": project_metadata.model_dump(mode="json")
                if hasattr(project_metadata, "model_dump")
                else project_metadata,
                "attachments_text": attachments_text or "",
                "conversation_history": conversation_history or [],
            },
            sort_keys=True,
        )
    semantic_mode = settings.semantic_cache_mode
    semantic_bucket = build_semantic_bucket(
        prompt_version=prompt_version,
        project_type=request.project_type.value,
        detail_level=request.detail_level.value,
        output_format=request.output_format.value,
        model_identity=effective_tier,
    )
    semantic_metadata = _semantic_shadow_disabled_metadata(semantic_mode)

    combined_prompt_identity = (
        f"prompt_version={prompt_version}\n"
        f"structured_system_prompt={system_prompt}\n\n"
        f"template_system_prompt={template_system_prompt}\n\n"
        f"--- user prompt ---\n"
        f"{user_prompt}"
    )

    def model_call() -> dict:
        nonlocal semantic_metadata

        if semantic_mode == "shadow":
            semantic_metadata = build_semantic_shadow_cache().lookup(
                bucket=semantic_bucket,
                text=request.description,
            )
            logger.info(
                "Semantic cache shadow lookup "
                f"candidate_found={semantic_metadata.get('candidate_found')}, "
                f"similarity={semantic_metadata.get('similarity')}, "
                f"bucket={semantic_metadata.get('bucket')}"
            )

        logger.info(
            "Calling LiteLLM structured product estimator "
            f"starting_tier={effective_tier}, model={resolved.model}, "
            f"prompt_version={prompt_version}"
        )
        provider_result = provider.complete_structured_messages_with_fallback(
            messages=messages,
            starting_tier=effective_tier,
            tier_ladder=settings.tier_ladder,
            response_model=EstimationResult,
            max_tokens=2000,
        )

        served_tier = provider_result.get("tier")
        fallback_used = bool(provider_result.get("fallback_used", served_tier != effective_tier))
        logger.info(
            "Structured product estimator completed "
            f"requested_tier={effective_tier}, served_tier={served_tier}, "
            f"fallback_used={fallback_used}, provider={provider_result.get('provider')}, "
            f"model={provider_result.get('model')}"
        )

        structured_result = EstimationResult.model_validate(provider_result["result"])
        output_guardrail_decision = evaluate_output_guardrails(structured_result)
        if not output_guardrail_decision.allowed:
            logger.warning(
                "blocked_structured_estimation_output reason_code=%s",
                output_guardrail_decision.reason_code,
            )
            raise RuntimeError(output_guardrail_decision.message)

        response_payload = {
            "result": structured_result.model_dump(mode="json"),
            "text": _estimation_result_to_text(structured_result),
            "model": provider_result.get("model"),
            "tier": served_tier,
            "provider": provider_result.get("provider"),
            "input_tokens": provider_result.get("input_tokens"),
            "output_tokens": provider_result.get("output_tokens"),
            "cost_usd": provider_result.get("cost_usd"),
            "cost_source": provider_result.get("cost_source"),
            "pricing_model": provider_result.get("pricing_model"),
            "finish_reason": provider_result.get("finish_reason"),
            "requested_tier": effective_tier,
            "served_tier": served_tier,
            "fallback_used": fallback_used,
            "semantic_cache_mode": semantic_metadata.get("mode", semantic_mode),
            "semantic_candidate_found": semantic_metadata.get("candidate_found", False),
            "semantic_candidate_key": semantic_metadata.get("candidate_key"),
            "semantic_similarity": semantic_metadata.get("similarity"),
            "semantic_bucket": semantic_metadata.get("bucket", semantic_bucket),
            "timestamp": provider_result.get("timestamp"),
        }

        if semantic_mode == "shadow":
            build_semantic_shadow_cache().store(
                bucket=semantic_bucket,
                text=request.description,
                payload=response_payload,
            )

        return response_payload

    cached_or_fresh = estimate_with_exact_cache(
        transcription=cache_identity,
        tier=effective_tier,
        model=resolved.model,
        system_prompt=combined_prompt_identity,
        cache=cache,
        model_call=model_call,
    )

    structured_result = EstimationResult.model_validate(cached_or_fresh["result"])
    text = cached_or_fresh.get("text") or _estimation_result_to_text(structured_result)

    served_tier = cached_or_fresh.get("served_tier", cached_or_fresh.get("tier"))

    return {
        "prompt_version": prompt_version,
        "result": structured_result,
        "text": text,
        "cached": cached_or_fresh.get("cached"),
        "cache_backend": cached_or_fresh.get("cache_backend"),
        "model": cached_or_fresh.get("model"),
        "provider": cached_or_fresh.get("provider"),
        "tier": served_tier,
        "input_tokens": cached_or_fresh.get("input_tokens"),
        "output_tokens": cached_or_fresh.get("output_tokens"),
        "cost_usd": cached_or_fresh.get("cost_usd"),
        "cost_source": cached_or_fresh.get("cost_source"),
        "pricing_model": cached_or_fresh.get("pricing_model"),
        "finish_reason": cached_or_fresh.get("finish_reason"),
        "timestamp": cached_or_fresh.get("timestamp"),
        "requested_tier": cached_or_fresh.get("requested_tier", effective_tier),
        "served_tier": served_tier,
        "fallback_used": cached_or_fresh.get("fallback_used", served_tier != effective_tier),
        "semantic_cache_mode": cached_or_fresh.get("semantic_cache_mode", semantic_mode),
        "semantic_candidate_found": cached_or_fresh.get("semantic_candidate_found", False),
        "semantic_candidate_key": cached_or_fresh.get("semantic_candidate_key"),
        "semantic_similarity": cached_or_fresh.get("semantic_similarity"),
        "semantic_bucket": cached_or_fresh.get("semantic_bucket"),
    }


def estimate_stream(
    transcription: str,
    tier: TierName | None = None,
    history: list[ConversationTurn] | None = None,
    max_history_turns: int = 6,
):
    """
    Stream estimation tokens through the LiteLLM provider abstraction.

    LAYER: services
    RESPONSIBILITY: Build the CAG prompt and delegate streaming to LiteLLMProvider.
    WHY IT EXISTS: Keeps streaming provider details out of FastAPI and Streamlit.
    DEPENDS ON: build_system_prompt, LiteLLMProvider.
    """
    system_prompt = build_system_prompt()
    effective_tier = tier or settings.llm_tier
    provider = LiteLLMProvider()

    logger.info(f"Streaming with LiteLLM tier={effective_tier}")

    yield from provider.stream(
        transcription=transcription,
        system_prompt=system_prompt,
        tier=effective_tier,
        max_tokens=2000,
        history=history,
        max_history_turns=max_history_turns,
    )

