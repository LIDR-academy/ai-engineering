"""
LAYER: schemas

Responsibility:
Define Pydantic request and response models for both the legacy Session 03
transcription flow and the typed Session 04 product flow.

Why this exists:
Routers should stay thin. The schema layer validates HTTP payloads at the edge,
documents the OpenAPI contract, and protects the UI and cache from malformed
model output.
"""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.services.conversation import ConversationTurn


class EstimateRequest(BaseModel):
    """Legacy inbound payload for the transcription based Session 03 endpoint."""

    transcription: str = Field(
        ...,
        min_length=10,
        description="Meeting transcription text used by the legacy estimator flow.",
    )
    tier: str = Field(
        default="flash",
        description="Logical LLM tier: flash, pro, backup, or backup_pro.",
    )
    history: list[ConversationTurn] | None = Field(
        default=None,
        description="Optional previous visible conversation turns.",
    )
    max_history_turns: int = Field(
        default=6,
        ge=0,
        le=20,
        description="Maximum previous turns to include in the LLM prompt.",
    )


class EstimateResponse(BaseModel):
    """Legacy outbound payload with markdown estimation and model metadata."""

    estimation: str = Field(..., description="Generated estimation in markdown.")
    model: str = Field(..., description="Specific model that answered.")
    tier: str = Field(..., description="Logical tier used.")
    provider: str = Field(..., description="LLM provider name.")
    input_tokens: int = Field(..., description="Input token count.")
    output_tokens: int = Field(..., description="Output token count.")
    timestamp: str = Field(..., description="UTC ISO 8601 response timestamp.")
    cached: bool = Field(default=False, description="True when exact cache served the response.")
    cache_backend: str = Field(
        default="unknown",
        description="Cache backend used: redis, memory_fallback, or unknown.",
    )
    cost_usd: float | None = Field(default=None, description="Estimated LLM call cost in USD.")
    cost_source: str | None = Field(
        default=None,
        description="How cost was derived: static_estimate, missing_token_usage, unknown_pricing.",
    )
    pricing_model: str | None = Field(default=None, description="Model id used for cost lookup.")




class TurnObservation(BaseModel):
    """Aggregate Session 06 CAG stress observation emitted once per turn.

    WHY IT EXISTS:
    The stress runner needs one stable, parseable shape instead of reconciling
    separate cache, provider, history, and request logs after the fact.
    This is measurement instrumentation only, not a CAG optimization.
    """

    turn_index: int = Field(ge=1)
    session_id: str
    enriched_transcript_chars: int = Field(ge=0)
    attachments_total_chars: int = Field(ge=0)
    messages_in_window: int = Field(ge=0)
    anchors_count: int = Field(default=0, ge=0)
    summary_chars: int = Field(default=0, ge=0)
    tokens_in: int = Field(default=0, ge=0)
    tokens_out: int = Field(default=0, ge=0)
    cost_usd: float = Field(default=0.0, ge=0)
    latency_ms: int = Field(default=0, ge=0)
    cache_hit_kind: Literal["none", "exact", "semantic"] = "none"
    last_resolved_tier: str = "default"


class ProjectType(StrEnum):
    """Typed project categories accepted by the Session 04 product interface."""

    MOBILE_APP = "mobile_app"
    WEB_SAAS = "web_saas"
    INTERNAL_TOOL = "internal_tool"
    DATA_PIPELINE = "data_pipeline"


class DetailLevel(StrEnum):
    """Supported estimation detail levels for the typed product flow."""

    SUMMARY = "summary"
    MEDIUM = "medium"
    DETAILED = "detailed"


class OutputFormat(StrEnum):
    """Supported output formats requested by the typed product flow."""

    PHASES_TABLE = "phases_table"
    LINE_ITEMS = "line_items"
    NARRATIVE = "narrative"


class ReferenceProject(BaseModel):
    """Optional similar project supplied by the user for prompt calibration."""

    name: str = Field(min_length=2, max_length=120)
    summary: str = Field(min_length=10, max_length=800)
    estimated_hours: int | None = Field(default=None, ge=1, le=10000)
    notes: str | None = Field(default=None, max_length=800)


class EstimationRequest(BaseModel):
    """Typed estimation request used by the Session 04 product form."""

    description: str = Field(min_length=20, max_length=2000)
    project_type: ProjectType
    detail_level: DetailLevel
    output_format: OutputFormat
    reference_projects: list[ReferenceProject] | None = None
    tier: Literal["flash", "pro", "backup", "backup_pro"] | None = Field(
        default=None,
        description="Optional starting LLM tier selected by the product UI.",
    )


class Phase(BaseModel):
    """
    One structured delivery phase in an estimation.

    Why it exists:
    The frontend should render fields, not parse markdown tables. A Phase gives
    Streamlit stable data for tables, cards, metrics, validation, and cache rules.
    """

    name: str = Field(min_length=2, max_length=120)
    summary: str = Field(min_length=10, max_length=1000)
    duration_weeks: float = Field(ge=0, le=260)
    cost_eur: int = Field(ge=0, le=10_000_000)
    confidence_pct: int = Field(ge=0, le=100)
    tasks: list[str] = Field(min_length=1)
    risks: list[str] = Field(default_factory=list)


class EstimationResult(BaseModel):
    """
    Structured product estimate returned by the live Session 04 pipeline.

    Why it exists:
    This is the move from prose to data. Pydantic catches malformed model output
    before the UI renders it or the cache stores it.
    """

    summary: str = Field(min_length=10, max_length=2000)
    project_type: ProjectType
    detail_level: DetailLevel
    output_format: OutputFormat
    total_duration_weeks: float = Field(ge=0, le=260)
    total_cost_eur: int = Field(ge=0, le=10_000_000)
    confidence_pct: int = Field(ge=0, le=100)
    phases: list[Phase] = Field(min_length=1)
    assumptions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_totals_and_confidence(self) -> "EstimationResult":
        """
        Validate business invariants that individual fields cannot check alone.

        Cost rule:
        The total must equal the sum of phase costs.

        Duration rule:
        Phases can overlap, so total duration must be at least the longest phase
        and at most the sum of all phase durations.

        Confidence rule:
        Low confidence estimates must visibly warn the user.
        """

        phase_cost_total = sum(phase.cost_eur for phase in self.phases)
        if phase_cost_total != self.total_cost_eur:
            raise ValueError("total_cost_eur must equal the sum of phase cost_eur values")

        phase_duration_sum = sum(phase.duration_weeks for phase in self.phases)
        longest_phase_duration = max(phase.duration_weeks for phase in self.phases)

        if not longest_phase_duration <= self.total_duration_weeks <= phase_duration_sum:
            raise ValueError(
                "total_duration_weeks must be between the longest phase duration "
                "and the sum of all phase durations"
            )

        if self.confidence_pct < 50 and not self.summary.startswith("Out of scope:"):
            raise ValueError(
                'low confidence estimates must start summary with "Out of scope:"'
            )

        return self


class EstimationResponse(BaseModel):
    """
    Typed product response for Session 04.

    result is the structured live Session 04 contract.
    text remains optional compatibility for older markdown-oriented callers.
    The UI should prefer result when present.
    """

    prompt_version: str
    result: EstimationResult | None = None
    text: str | None = None
    cached: bool | None = None
    cache_backend: str | None = None
    model: str | None = None
    provider: str | None = None
    tier: str | None = None
    requested_tier: str | None = None
    served_tier: str | None = None
    fallback_used: bool | None = None
    semantic_cache_mode: str | None = None
    semantic_candidate_found: bool | None = None
    semantic_candidate_key: str | None = None
    semantic_similarity: float | None = None
    semantic_bucket: str | None = None
