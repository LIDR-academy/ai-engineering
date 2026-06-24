"""
Output guardrails for structured Session 04 estimation results.

LAYER: guardrails
RESPONSIBILITY: Detect unsafe or poorly framed structured model output before it
                reaches the cache or UI.
WHY IT EXISTS: Pydantic validates shape and numeric invariants. Output guardrails
               validate product safety semantics such as prompt leakage wording.
DEPENDS ON: dataclasses, re, EstimationResult.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.schemas.estimation import EstimationResult


@dataclass(frozen=True)
class OutputGuardrailDecision:
    """
    Result of output guardrail evaluation.

    allowed:
    True when the structured estimate can be cached and returned.

    reason_code and message:
    Stable diagnostic fields for service and API error handling.
    """

    allowed: bool
    reason_code: str | None = None
    message: str | None = None


_ALLOWED = OutputGuardrailDecision(allowed=True)

_SYSTEM_PROMPT_LEAK_RE = re.compile(
    r"\b("
    r"system prompt|developer message|hidden instruction|hidden prompt|"
    r"internal instruction|reveal hidden|leak prompt"
    r")\b",
    re.IGNORECASE,
)


def evaluate_output_guardrails(result: EstimationResult | dict[str, Any]) -> OutputGuardrailDecision:
    """
    Evaluate a structured estimation result.

    The function accepts either an EstimationResult or a dict so tests can verify
    safety rules even when Pydantic would reject a shape first.

    Guardrails here are deliberately deterministic:
    low confidence framing and prompt leakage language.
    """

    payload = result.model_dump(mode="json") if isinstance(result, EstimationResult) else result

    summary = str(payload.get("summary", ""))
    confidence = payload.get("confidence_pct")

    if isinstance(confidence, int | float) and confidence < 50 and not summary.startswith(
        "Out of scope:"
    ):
        return OutputGuardrailDecision(
            allowed=False,
            reason_code="low_confidence_unframed",
            message='Output guardrails blocked model output: low confidence must start with "Out of scope:".',
        )

    searchable_text = "\n".join(_iter_text_fields(payload))
    if _SYSTEM_PROMPT_LEAK_RE.search(searchable_text):
        return OutputGuardrailDecision(
            allowed=False,
            reason_code="system_prompt_leak",
            message="Output guardrails blocked model output: possible system prompt leakage text detected.",
        )

    return _ALLOWED


def _iter_text_fields(value: Any):
    """Yield all string values from nested structured output."""

    if isinstance(value, str):
        yield value
        return

    if isinstance(value, dict):
        for child in value.values():
            yield from _iter_text_fields(child)
        return

    if isinstance(value, list):
        for child in value:
            yield from _iter_text_fields(child)
