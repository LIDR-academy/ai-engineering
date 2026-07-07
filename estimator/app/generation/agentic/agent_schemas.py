"""Pydantic contracts for the Session 12 manual estimation agent."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Literal

from pydantic import BaseModel, Field

AgentStatus = Literal["done", "max_steps_exceeded", "error"]
ComponentType = Literal[
    "backend",
    "integration",
    "mobile",
    "analytics",
    "frontend",
    "migration",
]

ToolFn = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class DateRangeFilter(BaseModel):
    """Optional project-year bounds passed through to retrieval metadata filters."""

    year_min: int | None = None
    year_max: int | None = None


class SearchBudgetsFilters(BaseModel):
    """Optional filters for a single-component budget search."""

    component_type: ComponentType | None = None
    sectors: list[str] | None = None
    date_range: DateRangeFilter | None = None


class SearchBudgetsArgs(BaseModel):
    """Arguments the model passes to ``search_budgets``."""

    query: str = Field(description="Focused description of one component to price.")
    filters: SearchBudgetsFilters | None = None


class CalculateComponentInput(BaseModel):
    """One component handed to the deterministic costing tool."""

    name: str
    reference_amounts: list[float] = Field(default_factory=list)


class CalculateEstimateArgs(BaseModel):
    """Arguments the model passes to ``calculate_estimate``."""

    components: list[CalculateComponentInput]


class AgentStep(BaseModel):
    """One iteration of the manual agent loop (reason → act → observe)."""

    step: int
    reasoning: str
    action: str
    observation: str


class ComponentBreakdown(BaseModel):
    """Per-component line in a deterministic costing result."""

    name: str
    reference_count: int
    estimated_hours: float
    unbudgeted: bool


class CalculateEstimateResult(BaseModel):
    """Structured output from the ``calculate_estimate`` tool."""

    components: list[ComponentBreakdown]
    total_hours: float
    summary: str


class ComponentEstimate(BaseModel):
    """One priced component in the final agent estimate."""

    name: str
    estimated_hours: float
    reference_budget_ids: list[str] = Field(default_factory=list)
    unbudgeted: bool = False


class AgentEstimate(BaseModel):
    """Final structured estimate returned by the agent."""

    components: list[ComponentEstimate]
    total_hours: float
    notes: str = ""


class AgentResult(BaseModel):
    """Outcome of a full agent run, including the step-by-step trace."""

    status: AgentStatus
    estimate: AgentEstimate | None = None
    trace: list[AgentStep] = Field(default_factory=list)
    final_message: str | None = None
    error: str | None = None
