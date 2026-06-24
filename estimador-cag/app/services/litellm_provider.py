"""
LAYER: services (provider abstraction)
RESPONSIBILITY: Resolve logical LLM tiers into LiteLLM compatible model settings.
WHY IT EXISTS: Keeps provider/model routing separate from business logic and prepares
               Session 03 canonical LiteLLM integration.
DEPENDS_ON: dataclasses, app.config.settings

ARCHITECTURE NOTE:
This module does not call the LLM yet. It only defines the provider routing contract.
The actual LiteLLM call is introduced in a later TDD slice.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime

import litellm
from pydantic import BaseModel, ValidationError

from app.config import TierName, settings
from app.services.conversation import ConversationTurn, build_conversation_messages
from app.services.costs import estimate_cost_usd


@dataclass(frozen=True)
class ResolvedModel:
    """Resolved provider configuration for a logical LLM tier."""

    tier: TierName
    provider: str
    model: str
    api_key: str
    base_url: str
    temperature: float



def _litellm_model_name(*, provider: str, model: str) -> str:
    """
    Convert configured model names into LiteLLM provider routed model names.

    LAYER: services
    RESPONSIBILITY: Keep env config human readable while giving LiteLLM the provider prefix it needs.
    WHY IT EXISTS: LiteLLM routes Moonshot/Kimi models through the moonshot/ provider prefix.
    DEPENDS_ON: LiteLLM provider naming conventions.
    """
    if provider == "kimi" and not model.startswith("moonshot/"):
        return f"moonshot/{model}"
    return model

class LiteLLMProvider:
    """
    Resolve application tiers into provider specific LiteLLM settings.

    LAYER: services
    RESPONSIBILITY: Convert flash/pro/backup/backup_pro into concrete model config.
    WHY IT EXISTS: Gives llm_service.py a provider agnostic routing interface.
    DEPENDS_ON: app.config.settings
    """

    def resolve_model(self, tier: TierName) -> ResolvedModel:
        """Return model settings for the requested logical tier."""
        if tier == "flash":
            return ResolvedModel(
                tier="flash",
                provider="deepseek",
                model=settings.deepseek_model,
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
                temperature=0.3,
            )

        if tier == "pro":
            return ResolvedModel(
                tier="pro",
                provider="deepseek",
                model=settings.deepseek_model_pro,
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
                temperature=0.3,
            )

        if tier == "backup":
            return ResolvedModel(
                tier="backup",
                provider="kimi",
                model=_litellm_model_name(provider="kimi", model=settings.kimi_model),
                api_key=settings.kimi_api_key,
                base_url=settings.kimi_base_url,
                temperature=1.0,
            )

        if tier == "backup_pro":
            return ResolvedModel(
                tier="backup_pro",
                provider="kimi",
                model=_litellm_model_name(provider="kimi", model=settings.kimi_model_pro),
                api_key=settings.kimi_api_key,
                base_url=settings.kimi_base_url,
                temperature=1.0,
            )

        raise ValueError(f"Unknown tier: {tier}")

    def complete(
        self,
        *,
        transcription: str,
        system_prompt: str,
        tier: TierName,
        max_tokens: int = 2000,
        history: list[ConversationTurn] | None = None,
        max_history_turns: int = 6,
    ) -> dict:
        """
        Execute a synchronous LiteLLM completion for one logical tier.

        LAYER: services
        RESPONSIBILITY: Call LiteLLM and normalize response metadata.
        WHY IT EXISTS: Gives llm_service.py one provider agnostic completion API.
        DEPENDS_ON: litellm.completion, resolve_model.
        """
        resolved = self.resolve_model(tier)
        messages = build_conversation_messages(
            system_prompt=system_prompt,
            transcription=transcription,
            history=history,
            max_history_turns=max_history_turns,
        )

        response = litellm.completion(
            model=resolved.model,
            messages=messages,
            api_key=resolved.api_key,
            api_base=resolved.base_url,
            temperature=resolved.temperature,
            max_tokens=max_tokens,
        )

        raw_content = response.choices[0].message.content
        content = self._clean_estimation_content(raw_content)
        if not content or not content.strip():
            raise RuntimeError(
                f"Empty response content from model={resolved.model}, tier={resolved.tier}. "
                "Provider returned tokens but no visible estimation."
            )

        usage = response.usage
        input_tokens = usage.prompt_tokens
        output_tokens = usage.completion_tokens
        finish_reason = getattr(response.choices[0], "finish_reason", None)
        cost = estimate_cost_usd(
            model=resolved.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        return {
            "estimation": content,
            "model": resolved.model,
            "tier": resolved.tier,
            "provider": resolved.provider,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost["cost_usd"],
            "cost_source": cost["cost_source"],
            "pricing_model": cost["pricing_model"],
            "finish_reason": finish_reason,
            "timestamp": datetime.now(UTC).isoformat(),
        }


    def complete_messages(
        self,
        *,
        messages: list[dict[str, str]],
        tier: TierName,
        max_tokens: int = 2000,
    ) -> dict:
        """
        Execute a synchronous LiteLLM completion from explicit chat messages.

        LAYER: services
        RESPONSIBILITY: Send already-rendered system and user messages without
                        rebuilding or concatenating prompts.
        WHY IT EXISTS: Session 04 moves prompting into templates, so the provider
                       needs a message-native API.
        DEPENDS_ON: litellm.completion, resolve_model.
        """
        resolved = self.resolve_model(tier)

        response = litellm.completion(
            model=resolved.model,
            messages=messages,
            api_key=resolved.api_key,
            api_base=resolved.base_url,
            temperature=resolved.temperature,
            max_tokens=max_tokens,
        )

        raw_content = response.choices[0].message.content
        content = self._clean_estimation_content(raw_content)
        if not content or not content.strip():
            raise RuntimeError(
                f"Empty response content from model={resolved.model}, tier={resolved.tier}. "
                "Provider returned tokens but no visible estimation."
            )

        usage = response.usage
        input_tokens = usage.prompt_tokens
        output_tokens = usage.completion_tokens
        finish_reason = getattr(response.choices[0], "finish_reason", None)
        cost = estimate_cost_usd(
            model=resolved.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        return {
            "estimation": content,
            "model": resolved.model,
            "tier": resolved.tier,
            "provider": resolved.provider,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost["cost_usd"],
            "cost_source": cost["cost_source"],
            "pricing_model": cost["pricing_model"],
            "finish_reason": finish_reason,
            "timestamp": datetime.now(UTC).isoformat(),
        }

    def complete_structured_messages(
        self,
        *,
        messages: list[dict[str, str]],
        tier: TierName,
        response_model: type[BaseModel],
        max_tokens: int = 2000,
    ) -> dict:
        """
        Execute a synchronous LiteLLM structured completion from explicit messages.

        LAYER: services
        RESPONSIBILITY: Validate provider output into a Pydantic response model.
        WHY IT EXISTS: Session 04 product UI needs fields, not markdown parsing.
        DEPENDS_ON: litellm.completion, resolve_model, Pydantic validation.

        Design note:
        Routers and UI should not care whether the provider returned a JSON
        string, a dictionary, or an already parsed object. This method normalizes
        those shapes and returns a trusted model under result.
        """

        resolved = self.resolve_model(tier)

        structured_messages = self._messages_with_json_schema_contract(
            messages=messages,
            response_model=response_model,
        )

        response = litellm.completion(
            model=resolved.model,
            messages=structured_messages,
            api_key=resolved.api_key,
            api_base=resolved.base_url,
            temperature=resolved.temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )

        try:
            result = self._validated_structured_result(
                response=response,
                response_model=response_model,
            )
            final_response = response
        except (ValidationError, TypeError, ValueError) as exc:
            raw_content = self._extract_raw_message_content(response)
            if not raw_content:
                raise RuntimeError(f"Invalid structured payload from {resolved.model}: {exc}") from exc

            repair_response = self._repair_structured_response(
                raw_content=raw_content,
                response_model=response_model,
                resolved=resolved,
                max_tokens=max_tokens,
            )

            try:
                result = self._validated_structured_result(
                    response=repair_response,
                    response_model=response_model,
                )
                final_response = repair_response
            except (ValidationError, TypeError, ValueError) as repair_exc:
                raise RuntimeError(
                    f"Invalid structured payload from {resolved.model} after repair: {repair_exc}"
                ) from repair_exc

        usage = self._extract_usage(final_response)
        input_tokens = usage["input_tokens"]
        output_tokens = usage["output_tokens"]
        finish_reason = self._extract_finish_reason(response)
        cost = estimate_cost_usd(
            model=resolved.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        return {
            "result": result,
            "model": resolved.model,
            "tier": resolved.tier,
            "provider": resolved.provider,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost["cost_usd"],
            "cost_source": cost["cost_source"],
            "pricing_model": cost["pricing_model"],
            "finish_reason": finish_reason,
            "timestamp": datetime.now(UTC).isoformat(),
        }

    def _validated_structured_result(
        self,
        *,
        response,
        response_model: type[BaseModel],
    ) -> BaseModel:
        """Extract, normalize, and validate one structured provider response."""

        if isinstance(response, response_model):
            raw_payload = response
        else:
            raw_payload = self._extract_structured_payload(response)

        normalized_payload = self._normalize_structured_payload(
            raw_payload=raw_payload,
            response_model=response_model,
        )

        return response_model.model_validate(normalized_payload)

    def _repair_structured_response(
        self,
        *,
        raw_content: str,
        response_model: type[BaseModel],
        resolved: ResolvedModel,
        max_tokens: int,
    ):
        """Ask the same model to convert non JSON visible output into the schema."""

        schema_text = json.dumps(
            response_model.model_json_schema(),
            ensure_ascii=False,
            sort_keys=True,
        )

        repair_messages = [
            {
                "role": "system",
                "content": (
                    "You are a strict JSON repair adapter. "
                    "Return only valid JSON. Return exactly one JSON object. "
                    "No headings, no bullets, no prose, no code fences."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Convert the model output below into a JSON object that validates "
                    "against this JSON schema. Preserve the estimate content as much as possible.\n\n"
                    f"JSON schema:\n{schema_text}\n\n"
                    f"<model_output>\n{raw_content[:8000]}\n</model_output>"
                ),
            },
        ]

        return litellm.completion(
            model=resolved.model,
            messages=repair_messages,
            api_key=resolved.api_key,
            api_base=resolved.base_url,
            temperature=resolved.temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )

    @staticmethod
    def _extract_raw_message_content(response) -> str | None:
        """Return visible model text for repair attempts."""

        try:
            message = LiteLLMProvider._extract_first_message(response)
        except Exception:
            return None

        content = LiteLLMProvider._get_value(message, "content")
        if isinstance(content, str) and content.strip():
            return content.strip()

        if isinstance(content, dict):
            return json.dumps(content, ensure_ascii=False)

        if isinstance(content, BaseModel):
            return content.model_dump_json()

        return None

    def complete_structured_messages_with_fallback(
        self,
        *,
        messages: list[dict[str, str]],
        starting_tier: TierName,
        tier_ladder: list[TierName],
        response_model: type[BaseModel],
        max_tokens: int = 2000,
    ) -> dict:
        """
        Execute a structured LiteLLM completion with tier fallback.

        LAYER: services
        RESPONSIBILITY: Try the requested structured tier and escalate safely.
        WHY IT EXISTS: Structured output should preserve the existing provider
                       abstraction and fallback discipline.
        DEPENDS_ON: complete_structured_messages.
        """

        start_idx = tier_ladder.index(starting_tier)
        tiers_to_try = tier_ladder[start_idx:]
        errors: list[str] = []

        for index, tier in enumerate(tiers_to_try):
            try:
                result = self.complete_structured_messages(
                    messages=messages,
                    tier=tier,
                    response_model=response_model,
                    max_tokens=max_tokens,
                )
                result["fallback_used"] = index > 0
                return result
            except Exception as exc:
                errors.append(f"{tier}: {exc}")
                continue

        raise RuntimeError(f"All structured LLM tiers failed: {'; '.join(errors)}")

    def complete_with_fallback_messages(
        self,
        *,
        messages: list[dict[str, str]],
        starting_tier: TierName,
        tier_ladder: list[TierName],
        max_tokens: int = 2000,
    ) -> dict:
        """
        Execute a message-native LiteLLM completion with tier fallback.

        LAYER: services
        RESPONSIBILITY: Try the requested tier and escalate while preserving the
                        exact rendered system and user messages.
        WHY IT EXISTS: Keeps Session 04 typed product prompting compatible with
                       the existing fallback ladder.
        DEPENDS_ON: complete_messages.
        """
        start_idx = tier_ladder.index(starting_tier)
        tiers_to_try = tier_ladder[start_idx:]
        errors: list[str] = []

        for index, tier in enumerate(tiers_to_try):
            try:
                result = self.complete_messages(
                    messages=messages,
                    tier=tier,
                    max_tokens=max_tokens,
                )
                result["fallback_used"] = index > 0
                return result
            except Exception as exc:
                errors.append(f"{tier}: {exc}")
                continue

        raise RuntimeError(f"All LLM tiers failed: {'; '.join(errors)}")

    def complete_with_fallback(
        self,
        *,
        transcription: str,
        system_prompt: str,
        starting_tier: TierName,
        tier_ladder: list[TierName],
        max_tokens: int = 2000,
        history: list[ConversationTurn] | None = None,
        max_history_turns: int = 6,
    ) -> dict:
        """
        Execute a synchronous LiteLLM completion with tier fallback.

        LAYER: services
        RESPONSIBILITY: Try the requested tier and escalate through configured tiers.
        WHY IT EXISTS: Keeps fallback behavior centralized and testable.
        DEPENDS_ON: complete.
        """
        start_idx = tier_ladder.index(starting_tier)
        tiers_to_try = tier_ladder[start_idx:]
        errors: list[str] = []

        for index, tier in enumerate(tiers_to_try):
            try:
                result = self.complete(
                    transcription=transcription,
                    system_prompt=system_prompt,
                    tier=tier,
                    max_tokens=max_tokens,
                )
                result["fallback_used"] = index > 0
                return result
            except Exception as exc:
                errors.append(f"{tier}: {exc}")
                continue

        raise RuntimeError(f"All LLM tiers failed: {'; '.join(errors)}")

    def stream(
        self,
        *,
        transcription: str,
        system_prompt: str,
        tier: TierName,
        max_tokens: int = 2000,
        history: list[ConversationTurn] | None = None,
        max_history_turns: int = 6,
    ):
        """
        Stream a LiteLLM completion for one logical tier.

        LAYER: services
        RESPONSIBILITY: Normalize LiteLLM streaming chunks into visible text tokens.
        WHY IT EXISTS: Keeps streaming provider behavior behind the same abstraction
                       as synchronous completion.

        FALLBACK POLICY:
        Some OpenAI-compatible providers can return a valid streaming response with
        no visible delta.content chunks. When that happens, we fallback to a normal
        synchronous completion and yield the complete visible answer once.
        """
        resolved = self.resolve_model(tier)
        messages = build_conversation_messages(
            system_prompt=system_prompt,
            transcription=transcription,
            history=history,
            max_history_turns=max_history_turns,
        )

        stream = litellm.completion(
            model=resolved.model,
            messages=messages,
            api_key=resolved.api_key,
            api_base=resolved.base_url,
            temperature=resolved.temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        emitted_any = False

        for chunk in stream:
            token = self._extract_stream_token(chunk)
            if token:
                emitted_any = True
                yield token

        if emitted_any:
            return

        fallback = self.complete(
            transcription=transcription,
            system_prompt=system_prompt,
            tier=tier,
            max_tokens=max_tokens,
            history=history,
            max_history_turns=max_history_turns,
        )
        yield fallback["estimation"]

    def verify_visible_output(
        self,
        *,
        tier: TierName,
        transcription: str,
        system_prompt: str,
        max_tokens: int = 800,
    ) -> dict:
        """
        Verify whether a tier returns non empty visible output.

        LAYER: services
        RESPONSIBILITY: Provide an explicit reliability check for suspicious tiers.
        WHY IT EXISTS: Kimi K2.6 can appear successful while returning no visible
                       content. This helper turns that behavior into measurable
                       reliability metadata instead of guesswork.
        DEPENDS_ON: complete.
        """
        resolved = self.resolve_model(tier)

        try:
            result = self.complete(
                transcription=transcription,
                system_prompt=system_prompt,
                tier=tier,
                max_tokens=max_tokens,
            )
            visible_output = bool(result.get("estimation", "").strip())

            return {
                "tier": tier,
                "provider": resolved.provider,
                "model": resolved.model,
                "visible_output": visible_output,
                "reliable": visible_output,
                "error_type": None,
                "error_message": None,
                "input_tokens": result.get("input_tokens"),
                "output_tokens": result.get("output_tokens"),
                "finish_reason": result.get("finish_reason"),
                "timestamp": result.get("timestamp"),
            }

        except Exception as exc:
            return {
                "tier": tier,
                "provider": resolved.provider,
                "model": resolved.model,
                "visible_output": False,
                "reliable": False,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "input_tokens": None,
                "output_tokens": None,
                "finish_reason": None,
                "timestamp": None,
            }

    @staticmethod
    def _messages_with_json_schema_contract(
        *,
        messages: list[dict[str, str]],
        response_model: type[BaseModel],
    ) -> list[dict[str, str]]:
        """
        Add a local JSON schema contract without sending Python classes to LiteLLM.

        WHY IT EXISTS:
        DeepSeek and Kimi through LiteLLM failed at runtime when receiving
        response_model=EstimationResult because the provider payload tried to
        JSON serialize a Pydantic ModelMetaclass.

        This keeps the provider call portable:
        normal chat messages go to LiteLLM, and Pydantic validation happens
        locally after the response is received.
        """

        schema = response_model.model_json_schema()
        schema_text = json.dumps(schema, ensure_ascii=False, sort_keys=True)

        contract = (
            "\n\nStructured output contract:\n"
            "Return only valid JSON. Do not use markdown fences. "
            "Do not add prose before or after the JSON.\n"
            f"JSON schema:\n{schema_text}"
        )

        copied = [message.copy() for message in messages]

        for message in copied:
            if message.get("role") == "system":
                message["content"] = f"{message.get('content', '')}{contract}"
                return copied

        return [{"role": "system", "content": contract.strip()}, *copied]

    @staticmethod
    def _extract_structured_payload(response):
        """
        Extract structured payload from common LiteLLM and Instructor shapes.

        WHY IT EXISTS:
        Provider libraries differ. Tests cover JSON strings, dictionaries, and
        already parsed Pydantic objects so the service layer gets one contract.
        """

        if isinstance(response, dict) and "choices" not in response:
            return response

        message = LiteLLMProvider._extract_first_message(response)

        parsed = LiteLLMProvider._get_value(message, "parsed")
        if parsed is not None:
            return parsed

        content = LiteLLMProvider._get_value(message, "content")

        if isinstance(content, BaseModel):
            return content

        if isinstance(content, dict):
            return content

        if isinstance(content, str):
            return LiteLLMProvider._parse_structured_json_content(content)

        raise ValueError("could not extract structured payload from provider response")

    @staticmethod
    def _normalize_structured_payload(*, raw_payload, response_model: type[BaseModel]):
        """
        Normalize deterministic aggregate fields before final schema validation.

        WHY IT EXISTS:
        LLMs are useful for estimating phase-level work but unreliable for exact
        arithmetic. The backend owns deterministic totals so valid phase plans do
        not fail only because a provider mis-added numbers.
        """

        if response_model.__name__ != "EstimationResult":
            return raw_payload

        if isinstance(raw_payload, BaseModel):
            raw_payload = raw_payload.model_dump(mode="json")

        if not isinstance(raw_payload, dict):
            return raw_payload

        phases = raw_payload.get("phases")
        if not isinstance(phases, list) or not phases:
            return raw_payload

        phase_costs: list[int] = []
        phase_durations: list[float] = []

        for phase in phases:
            if not isinstance(phase, dict):
                return raw_payload

            cost = phase.get("cost_eur")
            duration = phase.get("duration_weeks")

            if not isinstance(cost, int) or not isinstance(duration, (int, float)):
                return raw_payload

            phase_costs.append(cost)
            phase_durations.append(duration)

        normalized = raw_payload.copy()
        normalized["total_cost_eur"] = sum(phase_costs)
        normalized["total_duration_weeks"] = sum(phase_durations)
        return normalized

    @staticmethod
    def _parse_structured_json_content(content: str):
        """
        Parse structured JSON from model text.

        The prompt asks for JSON only, but this accepts common model slips such
        as fenced JSON blocks or surrounding whitespace.
        """

        cleaned = content.strip()

        if cleaned.startswith("```"):
            cleaned = cleaned.removeprefix("```json").removeprefix("```").strip()
            cleaned = cleaned.removesuffix("```").strip()

        try:
            return json.loads(cleaned)
        except Exception:
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(cleaned[start : end + 1])
                except Exception as exc:
                    raise ValueError("structured response content is not valid JSON") from exc

            raise ValueError("structured response content is not valid JSON")

    @staticmethod
    def _extract_first_message(response):
        """Return the first message from object style or dict style responses."""

        choices = LiteLLMProvider._get_value(response, "choices")
        if not choices:
            raise ValueError("provider response does not contain choices")

        first_choice = choices[0]
        message = LiteLLMProvider._get_value(first_choice, "message")
        if message is None:
            raise ValueError("provider response choice does not contain message")

        return message

    @staticmethod
    def _extract_usage(response) -> dict[str, int | None]:
        """Normalize token usage from object style or dict style responses."""

        usage = LiteLLMProvider._get_value(response, "usage")
        if usage is None:
            return {"input_tokens": None, "output_tokens": None}

        return {
            "input_tokens": LiteLLMProvider._get_value(usage, "prompt_tokens"),
            "output_tokens": LiteLLMProvider._get_value(usage, "completion_tokens"),
        }

    @staticmethod
    def _extract_finish_reason(response) -> str | None:
        """Normalize finish_reason from object style or dict style responses."""

        choices = LiteLLMProvider._get_value(response, "choices")
        if not choices:
            return None

        first_choice = choices[0]
        return LiteLLMProvider._get_value(first_choice, "finish_reason")

    @staticmethod
    def _get_value(container, key: str):
        """Read a value from either an object attribute or a dictionary key."""

        if isinstance(container, dict):
            return container.get(key)

        return getattr(container, key, None)

    @staticmethod
    def _clean_estimation_content(content: str | None) -> str | None:
        """
        Remove process-like preambles before the final estimation.

        WHY IT EXISTS: Some providers may return a visible preamble before the
        actual answer. The UI should show the final estimation, not the model's
        self-description of the task.
        """
        if content is None:
            return None

        markers = [
            "## Estimación",
            "## Estimacion",
            "### Desglose",
            "Desglose de tareas",
        ]

        positions = [content.find(marker) for marker in markers if content.find(marker) != -1]
        if not positions:
            return content

        start = min(positions)
        return content[start:].lstrip()

    @staticmethod
    def _extract_stream_token(chunk) -> str | None:
        """
        Extract visible token text from LiteLLM/OpenAI-compatible stream chunks.

        WHY IT EXISTS: Providers differ between object-style and dict-style chunks.
        """
        try:
            choice = chunk.choices[0]
        except (AttributeError, IndexError, TypeError):
            try:
                choice = chunk["choices"][0]
            except (KeyError, IndexError, TypeError):
                return None

        try:
            delta = choice.delta
        except AttributeError:
            delta = choice.get("delta", {}) if isinstance(choice, dict) else {}

        if isinstance(delta, dict):
            return delta.get("content")

        return getattr(delta, "content", None)

