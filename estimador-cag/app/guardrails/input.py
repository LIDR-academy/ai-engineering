"""
Input guardrails for typed Session 04 estimation requests.

LAYER: guardrails
RESPONSIBILITY: Detect unsafe or inappropriate user controlled text before cache
                lookup or provider calls.
WHY IT EXISTS: Guardrails are product safety checks. They reduce obvious prompt
               injection and PII leakage risks before the LLM sees the request.
DEPENDS ON: dataclasses, re.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class GuardrailDecision:
    """
    Result of an input guardrail evaluation.

    allowed:
    True when the request can continue to validation, cache, and provider call.

    reason_code and message:
    Clean product facing fields used by the API when a request is blocked.
    """

    allowed: bool
    reason_code: str | None = None
    message: str | None = None

    def to_detail(self) -> dict[str, str]:
        """Return a stable API detail payload for blocked requests."""

        return {
            "reason_code": self.reason_code or "blocked",
            "message": self.message or "Request blocked by input guardrails.",
        }


_ALLOWED = GuardrailDecision(allowed=True)

_SYSTEM_TAG_RE = re.compile(r"</?\s*system\b[^>]*>", re.IGNORECASE)

_SYSTEM_PROMPT_EXTRACTION_RE = re.compile(
    r"\b("
    r"reveal|show|print|dump|display|expose|leak"
    r")\b.{0,80}\b("
    r"system prompt|developer message|hidden prompt|instructions"
    r")\b",
    re.IGNORECASE,
)

_PROMPT_INJECTION_RE = re.compile(
    r"\b("
    r"ignore previous instructions|ignore all previous instructions|"
    r"disregard previous instructions|override instructions|"
    r"forget previous instructions|you are now|act as system|"
    r"bypass safety|jailbreak"
    r")\b",
    re.IGNORECASE,
)

_EMAIL_RE = re.compile(
    r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
    re.IGNORECASE,
)

_PHONE_RE = re.compile(
    r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)",
    re.IGNORECASE,
)


def evaluate_input_guardrails(text: str) -> GuardrailDecision:
    """
    Evaluate user controlled product description text.

    The rules are intentionally simple and deterministic in this phase:
    prompt injection patterns, system tag smuggling, and basic PII patterns.

    This does not replace schema validation. Pydantic still owns required fields,
    length limits, and enum validation.
    """

    if _SYSTEM_TAG_RE.search(text):
        return GuardrailDecision(
            allowed=False,
            reason_code="system_tag",
            message="Request blocked by input guardrails: system style tags are not allowed.",
        )

    if _SYSTEM_PROMPT_EXTRACTION_RE.search(text):
        return GuardrailDecision(
            allowed=False,
            reason_code="system_prompt_extraction",
            message="Request blocked by input guardrails: system prompt extraction is not allowed.",
        )

    if _PROMPT_INJECTION_RE.search(text):
        return GuardrailDecision(
            allowed=False,
            reason_code="prompt_injection",
            message="Request blocked by input guardrails: prompt injection text was detected.",
        )

    if _EMAIL_RE.search(text):
        return GuardrailDecision(
            allowed=False,
            reason_code="pii_email",
            message="Request blocked by input guardrails: remove email addresses before estimation.",
        )

    if _PHONE_RE.search(text):
        return GuardrailDecision(
            allowed=False,
            reason_code="pii_phone",
            message="Request blocked by input guardrails: remove phone numbers before estimation.",
        )

    return _ALLOWED
