"""Node-internal LLM I/O models for the graph.

These are the ``response_model``s the structured-output nodes hand to
``LLMWrapper.complete_structured`` (Instructor validates + re-prompts the LLM
against them). They are deliberately kept OUT of ``app/domain/schemas`` — that
package is the external contract with Rails; these are private plumbing of the
graph nodes. The public request/response contract lives in
``app/domain/schemas/graph_estimation.py``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Confidence = Literal["low", "medium", "high"]


class RequirementsExtraction(BaseModel):
    """Output of ``extract_requirements``: the flat list of requirements."""

    requirements: list[str] = Field(
        default_factory=list,
        description="Concrete, atomic functional/technical requirements the client "
        "wants, one per item, in concise technical English. Ignore small talk.",
    )


class ComponentModel(BaseModel):
    """One classified component (mirrors the ``Component`` TypedDict)."""

    name: str = Field(description="Short component name, e.g. 'Business backend API'.")
    category: str = Field(
        description="Coarse component category, e.g. 'backend', 'integration', "
        "'mobile', 'analytics', 'frontend', 'infrastructure'."
    )


class ComponentClassification(BaseModel):
    """Output of ``classify_components``: requirements grouped into components."""

    components: list[ComponentModel] = Field(default_factory=list)


class ComponentEstimate(BaseModel):
    """A single component's consolidated effort in the final estimate."""

    name: str
    engineer_days: int | None = Field(
        default=None,
        ge=0,
        description="Consolidated effort in engineer-days, as an INTEGER, in THIS "
        "field (not only in the rationale). Set it to the rounded median of the "
        "component's references converted to days. Use null ONLY when the component "
        "has NO references.",
    )
    rationale: str = Field(
        description="One line on how the number was derived from the references."
    )


class ConsolidatedEstimate(BaseModel):
    """Output of ``generate_estimate``: the structured estimate.

    Grounded in the ``budget_matches`` the graph accumulated (historical hours), so
    the numbers trace back to retrieved references rather than being invented.
    """

    components: list[ComponentEstimate] = Field(default_factory=list)
    total_engineer_days: int | None = Field(default=None, ge=0)
    confidence: Confidence = "medium"
    reasoning: str = Field(description="Short explanation of the consolidation.")


# --------------------------------------------------------------------------- #
# Session 13 (live) — the multi-agent nodes' LLM I/O models                   #
# --------------------------------------------------------------------------- #
Complexity = Literal["low", "medium", "high"]


class ComplexityClassification(BaseModel):
    """Output of ``classifier_agent``: complexity + a reformulated brief.

    The classifier reads the raw, messy meeting transcript and does two things at
    once: it judges HOW COMPLEX the estimation will be (which the graph maps to the
    structure agent's reasoning effort) and it REFORMULATES the transcript into a
    clean, self-contained project brief the rest of the flow can consume.
    """

    complexity: Complexity = Field(
        description="How complex the estimation is. 'low' = one simple component; "
        "'medium' = a few components; 'high' = many dispares components / integrations."
    )
    reformulated_transcript: str = Field(
        min_length=1,
        description="The transcript rewritten as a clean, self-contained project "
        "brief in technical English: the components the client wants, their scope and "
        "constraints, with the small talk and digressions removed. No invented scope.",
    )
    reasoning: str = Field(description="One line on why that complexity was assigned.")


class WeakPoint(BaseModel):
    """One weakness the analysis agent flags for the human's final review."""

    area: str = Field(description="Module/task or cross-cutting concern the weakness touches.")
    issue: str = Field(description="What is uncertain, ungrounded or contradictory.")
    severity: Literal["low", "medium", "high"] = "medium"


class ReliabilityReport(BaseModel):
    """Output of ``analysis_agent``: a data-reliability read of the estimate.

    Validates the hours the retrieval agent grounded and writes a short report that
    tells the human, before the final gate, HOW MUCH to trust the numbers and WHERE
    the estimate is weak (ungrounded tasks, contradictory analogs, low reliability).
    """

    overall_confidence: Literal["low", "medium", "high"] = Field(
        description="Overall confidence in the estimate as a whole."
    )
    grounded_task_ratio: float = Field(
        ge=0.0,
        le=1.0,
        description="Fraction of tasks that got hours from a historical match (0..1).",
    )
    weak_points: list[WeakPoint] = Field(
        default_factory=list,
        description="The specific soft spots the human should check or complete.",
    )
    summary: str = Field(description="A short prose read of the estimate's reliability.")


class CommercialProposal(BaseModel):
    """Output of ``proposal_agent`` (bonus): a client-facing commercial proposal."""

    title: str = Field(description="Proposal title, e.g. the project name.")
    executive_summary: str = Field(description="2-4 sentences a client executive would read.")
    scope: list[str] = Field(
        default_factory=list, description="Bullet scope: the modules/deliverables included."
    )
    total_engineer_days: int | None = Field(
        default=None, ge=0, description="Headline effort, echoed from the validated estimate."
    )
    body_markdown: str = Field(
        description="The full proposal as Markdown, grounded ONLY in the validated estimate."
    )


# --------------------------------------------------------------------------- #
# Session 14 — supervisor routing decision                                    #
# --------------------------------------------------------------------------- #
SupervisorNextAgent = Literal[
    "requirements_extractor",
    "budget_searcher",
    "estimate_generator",
    "coherence_validator",
    "finish",
]


class SupervisorDecision(BaseModel):
    """Structured output of the Session 14 supervisor router.

    ``next_agent`` is constrained to a closed ``Literal`` so an illegal destination
    is a schema failure (and then the legality guard / fallback), not a free-text
    hallucination that the graph cannot resolve.
    """

    next_agent: SupervisorNextAgent = Field(
        description="The specialist that must act next, or 'finish' when done."
    )
    reason: str = Field(description="Why this specialist, in one sentence.")
    confidence: Literal["low", "medium", "high"] | None = Field(
        default=None,
        description="How sure the router is about this choice (optional).",
    )
