"""
LAYER: services/session-memory
RESPONSIBILITY: Keep process-local conversational memory for Session 05.
WHY IT EXISTS: Session 05 needs project continuity across turns without adding
               a database or Redis-backed persistence yet.

The storage here is intentionally volatile. Sessions live only inside the
current Python process and disappear on restart, deploy, or multi-worker
reshuffle. That is acceptable for the pre-session exercise because the learning
objective is to separate conversation history from project metadata before we
introduce persistent memory or RAG.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from uuid import uuid4

from pydantic import BaseModel, Field

DEFAULT_MAX_TURNS = 6

TECHNOLOGY_KEYWORDS = [
    "FastAPI", "Streamlit", "PostgreSQL", "Redis", "Docker", "Kubernetes",
    "React", "Vue", "Angular", "Next.js", "Spring Boot", "Java", "Python",
    "TypeScript", "HubSpot", "Stripe", "OpenAI", "Anthropic", "DeepSeek",
    "Kimi", "Slack", "OAuth", "SAML", "AWS", "GCP", "Azure",
]


class ProjectMetadata(BaseModel):
    """Stable project facts kept separately from raw conversational turns."""

    project_name: str | None = Field(default=None, max_length=160)
    assumed_team_size: int | None = Field(default=None, ge=1, le=100)
    mentioned_technologies: list[str] = Field(default_factory=list)
    agreed_scope: str | None = Field(default=None, max_length=1200)
    open_questions: list[str] = Field(default_factory=list)
    attachments_seen: list[str] = Field(default_factory=list)

    def is_empty(self) -> bool:
        """Return True when no useful project facts have been captured yet."""

        return not self.model_dump(exclude_none=True, exclude_defaults=True)

    def to_prompt_block(self) -> str:
        """Render metadata as deterministic text for prompt injection."""

        if self.is_empty():
            return ""
        payload = self.model_dump(mode="json", exclude_none=True)
        lines: list[str] = []
        for key, value in payload.items():
            if value in (None, [], ""):
                continue
            rendered = ", ".join(str(item) for item in value) if isinstance(value, list) else str(value)
            lines.append(f"{key}: {rendered}")
        return "\n".join(lines)


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = value.strip()
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
    return result


def _clean_project_name(candidate: str) -> str:
    """Trim project-name captures so full sentences do not become names."""

    cleaned = candidate.strip()
    cleaned = cleaned.strip(".")
    cleaned = cleaned.strip()
    cleaned = cleaned.strip("'")
    cleaned = cleaned.strip(chr(34))
    cleaned = cleaned.strip()

    lines = cleaned.splitlines()
    if lines:
        cleaned = lines[0].strip()

    for separator in (".", "?", "!", ";", ":"):
        if separator in cleaned:
            cleaned = cleaned.split(separator, 1)[0].strip()

    stop_words = [
        " needs ",
        " need ",
        " requires ",
        " should ",
        " must ",
        " will ",
        " with ",
        " and ",
        " for ",
        " to ",
        " can ",
        " keep ",
        " scope ",
    ]
    lowered = f" {cleaned.lower()} "
    cut_positions = [
        lowered.find(stop_word)
        for stop_word in stop_words
        if lowered.find(stop_word) != -1
    ]
    if cut_positions:
        cleaned = cleaned[: min(cut_positions)].strip()

    return cleaned[:160]


def extract_project_name(text: str) -> str | None:
    """Extract a project name using cheap deterministic patterns."""

    patterns = [
        r"(?:project|producto|app|platform|system)\s+(?:called|named|codename|codename:|is called|se llama)\s+[\"']?([A-Z][A-Za-z0-9 ._-]{2,80})",
        r"(?:Project|Producto|App|Platform|System)\s*[:=]\s*[\"']?([A-Z][A-Za-z0-9 ._-]{2,80})",
        r"[\"']([A-Z][A-Za-z0-9 ._-]{2,60})[\"']\s+(?:project|platform|app|system)",
        r"\b([A-Z][A-Za-z0-9_-]+(?:\s+[A-Z][A-Za-z0-9_-]+){0,4})\s+(?:project|platform|app|system|scope)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            project_name = _clean_project_name(match.group(1))
            if project_name:
                return project_name
    return None

def extract_team_size(text: str) -> int | None:
    """Extract an assumed team size from transcript or model response text."""

    patterns = [
        r"(?:team|equipo)\s+(?:of|de)\s+(\d{1,2})",
        r"(\d{1,2})\s+(?:developers|engineers|devs|personas|people)",
        r"assumed_team_size\D+(\d{1,2})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            value = int(match.group(1))
            if 1 <= value <= 100:
                return value
    return None


def extract_technologies(text: str) -> list[str]:
    """Find known technology names in free text using a curated keyword list."""

    found: list[str] = []
    for technology in TECHNOLOGY_KEYWORDS:
        if re.search(rf"(?<![\w.+-]){re.escape(technology)}(?![\w.+-])", text, flags=re.IGNORECASE):
            found.append(technology)
    return _dedupe_preserve_order(found)


def extract_agreed_scope(text: str) -> str | None:
    """Capture a compact deterministic scope hint for project continuity."""

    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    scope_sentences = [
        sentence.strip()
        for sentence in sentences
        if re.search(
            r"\b(needs?|requires?|build|create|implement|include|scope|alcance|necesita|incluir)\b",
            sentence,
            flags=re.IGNORECASE,
        )
    ]
    if not scope_sentences:
        return None
    return " ".join(scope_sentences[:3])[:1200]


def extract_open_questions(text: str) -> list[str]:
    """Keep explicit question marks as lightweight unresolved questions."""

    questions = [sentence.strip() for sentence in re.split(r"(?<=\?)\s+", text) if "?" in sentence]
    return [question[:240] for question in questions[:5]]


@dataclass
class ConversationHistory:
    """Sliding-window user/assistant history for LiteLLM-compatible messages."""

    max_turns: int = DEFAULT_MAX_TURNS
    _turns: list[tuple[str, str]] = field(default_factory=list)

    def add_turn(self, user_content: str, assistant_content: str) -> None:
        """Append one user plus assistant turn and discard oldest overflow."""

        self._turns.append((user_content, assistant_content))
        overflow = len(self._turns) - self.max_turns
        if overflow > 0:
            del self._turns[:overflow]

    @property
    def turn_count(self) -> int:
        """Number of retained user plus assistant turns."""

        return len(self._turns)

    def to_messages_list(self, system_prompt: str) -> list[dict[str, str]]:
        """Return messages ready for LiteLLM, preserving system as invariant."""

        messages = [{"role": "system", "content": system_prompt}]
        for user_content, assistant_content in self._turns:
            messages.append({"role": "user", "content": user_content})
            messages.append({"role": "assistant", "content": assistant_content})
        return messages


@dataclass
class Session:
    """One volatile estimation conversation tracked by a UUID v4 id."""

    session_id: str
    history: ConversationHistory = field(default_factory=ConversationHistory)
    project_metadata: ProjectMetadata = field(default_factory=ProjectMetadata)
    last_turn_observed: dict | None = None
    total_turn_count: int = 0

    def add_turn(self, user_content: str, assistant_content: str) -> None:
        """Add a completed model turn to the retained sliding history."""

        self.total_turn_count += 1
        self.history.add_turn(user_content=user_content, assistant_content=assistant_content)

    def update_metadata(
        self,
        *,
        transcript: str,
        assistant_text: str,
        attachment_names: list[str] | None = None,
    ) -> ProjectMetadata:
        """Update project facts with deterministic, testable heuristics."""

        combined = f"{transcript}\n\n{assistant_text}"
        project_name = self.project_metadata.project_name or extract_project_name(combined)
        assumed_team_size = self.project_metadata.assumed_team_size or extract_team_size(combined)
        technologies = _dedupe_preserve_order(
            [*self.project_metadata.mentioned_technologies, *extract_technologies(combined)]
        )
        agreed_scope = extract_agreed_scope(transcript) or self.project_metadata.agreed_scope
        open_questions = _dedupe_preserve_order(
            [*self.project_metadata.open_questions, *extract_open_questions(transcript)]
        )[:10]
        attachments_seen = _dedupe_preserve_order(
            [*self.project_metadata.attachments_seen, *(attachment_names or [])]
        )
        self.project_metadata = ProjectMetadata(
            project_name=project_name,
            assumed_team_size=assumed_team_size,
            mentioned_technologies=technologies,
            agreed_scope=agreed_scope,
            open_questions=open_questions,
            attachments_seen=attachments_seen,
        )
        return self.project_metadata


class SessionStore:
    """In-memory session index. Volatile by design for this pre-session phase."""

    def __init__(self, *, max_turns: int = DEFAULT_MAX_TURNS) -> None:
        self.max_turns = max_turns
        self._sessions: dict[str, Session] = {}

    def create_session(self) -> Session:
        """Create and store a new empty session using UUID v4."""

        session = Session(session_id=str(uuid4()), history=ConversationHistory(max_turns=self.max_turns))
        self._sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> Session | None:
        """Return a session or None when the id is unknown."""

        return self._sessions.get(session_id)

    def require_session(self, session_id: str) -> Session:
        """Return a session or raise KeyError for router-level 404 handling."""

        session = self.get_session(session_id)
        if session is None:
            raise KeyError(session_id)
        return session

    def reset(self) -> None:
        """Clear all sessions. Intended for tests, not production workflows."""

        self._sessions.clear()


global_session_store = SessionStore()
