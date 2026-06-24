"""
LAYER: services (conversation management)
RESPONSIBILITY: Build bounded LLM message history for conversational estimation.
WHY IT EXISTS: Phase 6 adds conversation memory without letting Streamlit or FastAPI
               assemble prompts ad hoc.
DEPENDS_ON: pydantic
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

ConversationRole = Literal["user", "assistant"]


class ConversationTurn(BaseModel):
    """
    One previous visible conversation turn.

    System messages are intentionally rejected here. The canonical system prompt
    is controlled by build_conversation_messages and must remain first.
    """

    role: ConversationRole
    content: str = Field(..., min_length=1)

    @field_validator("role")
    @classmethod
    def reject_non_conversation_roles(cls, value: str) -> str:
        if value not in {"user", "assistant"}:
            raise ValueError("role must be user or assistant")
        return value


def build_conversation_messages(
    *,
    system_prompt: str,
    transcription: str,
    history: list[ConversationTurn] | None = None,
    max_history_turns: int = 6,
) -> list[dict[str, str]]:
    """
    Build OpenAI compatible messages with a bounded conversation window.

    The system prompt is always first. History is trimmed from the left, preserving
    the most recent turns. The current transcript is always appended last.
    """
    safe_history = history or []
    recent_history = safe_history[-max_history_turns:] if max_history_turns > 0 else []

    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]

    for turn in recent_history:
        messages.append({"role": turn.role, "content": turn.content})

    messages.append(
        {
            "role": "user",
            "content": f"TRANSCRIPCION DE REUNION:\n{transcription}",
        }
    )

    return messages


def summarize_conversation_stub(history: list[ConversationTurn]) -> dict[str, object]:
    """
    Placeholder for future summary compression.

    This is explicit so we do not pretend to have semantic summarization before
    implementing and testing it.
    """
    return {
        "status": "deferred",
        "turns_seen": len(history),
        "note": "Conversation summarization is reserved for a future compression step.",
    }
