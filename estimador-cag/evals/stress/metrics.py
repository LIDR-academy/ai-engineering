"""
Session 06 stress metrics for measuring where the CAG baseline degrades.

These metrics are deliberately deterministic. They do not use embeddings, RAG,
or LLM-as-judge because the exercise needs cheap, repeatable baseline curves.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MetricResult:
    """Minimal metric result compatible with the existing evals pattern."""

    name: str
    score: float
    passed: bool
    details: dict[str, Any] = field(default_factory=dict)


def _get_numeric(payload: dict[str, Any], key: str, default: float = 0.0) -> float:
    value = payload.get(key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class LatencyBudgetMetric:
    """Pass when one turn stays inside a latency budget in milliseconds."""

    name = "latency_budget"

    def __init__(self, budget_ms: int) -> None:
        self.budget_ms = budget_ms

    def evaluate(self, observation: dict[str, Any]) -> MetricResult:
        latency_ms = _get_numeric(observation, "latency_ms")
        passed = latency_ms <= self.budget_ms
        return MetricResult(
            name=self.name,
            score=1.0 if passed else 0.0,
            passed=passed,
            details={"latency_ms": latency_ms, "budget_ms": self.budget_ms},
        )


class CostBudgetMetric:
    """Pass when one turn stays inside a USD cost budget."""

    name = "cost_budget"

    def __init__(self, budget_usd: float) -> None:
        self.budget_usd = budget_usd

    def evaluate(self, observation: dict[str, Any]) -> MetricResult:
        cost_usd = _get_numeric(observation, "cost_usd")
        passed = cost_usd <= self.budget_usd
        return MetricResult(
            name=self.name,
            score=1.0 if passed else 0.0,
            passed=passed,
            details={"cost_usd": cost_usd, "budget_usd": self.budget_usd},
        )


class MemoryDriftMetric:
    """Pass when a required fact is still present in allowed snapshot fields."""

    name = "memory_drift"
    ALLOWED_FIELDS = {"summary", "anchors", "metadata"}

    def __init__(self, fact: str, where: list[str] | None = None) -> None:
        self.fact = fact
        self.where = where or ["summary", "anchors", "metadata"]
        unknown = set(self.where) - self.ALLOWED_FIELDS
        if unknown:
            raise ValueError(f"Unsupported snapshot fields for MemoryDriftMetric: {sorted(unknown)}")

    def evaluate(self, session_snapshot: dict[str, Any]) -> MetricResult:
        fact_folded = self.fact.casefold()
        haystacks = {field: self._field_text(session_snapshot, field) for field in self.where}
        matched_fields = [
            field for field, value in haystacks.items() if fact_folded in value.casefold()
        ]
        passed = bool(matched_fields)
        return MetricResult(
            name=self.name,
            score=1.0 if passed else 0.0,
            passed=passed,
            details={
                "fact": self.fact,
                "where": self.where,
                "matched_fields": matched_fields,
            },
        )

    def _field_text(self, snapshot: dict[str, Any], field: str) -> str:
        if field == "metadata":
            value = snapshot.get("project_metadata") or snapshot.get("metadata") or {}
        else:
            value = snapshot.get(field) or ""
        return self._stringify(value)

    def _stringify(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            return "\n".join(
                f"{key}: {self._stringify(item)}" for key, item in sorted(value.items())
            )
        if isinstance(value, list | tuple | set):
            return "\n".join(self._stringify(item) for item in value)
        return str(value)
