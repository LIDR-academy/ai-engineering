"""
Offline Session 10 retrieval evaluator.

This module evaluates A/B/C/D retrieval outputs without calling FastAPI,
PostgreSQL, OpenAI, DeepSeek, Kimi, or a reranker model. Runtime capture belongs
in a separate script; this file owns the deterministic scoring contract.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import median
from typing import Any

DEFAULT_GOLDEN_PATH = Path(__file__).with_name("golden_retrieval.json")
DEFAULT_K = 5


@dataclass(frozen=True)
class RetrievalConfig:
    """One Session 10 retrieval configuration."""

    config_id: str
    search_label: str
    search_mode: str
    use_reranker: bool
    notes: str


RETRIEVAL_CONFIGS: tuple[RetrievalConfig, ...] = (
    RetrievalConfig(
        config_id="A",
        search_label="Vector",
        search_mode="vector",
        use_reranker=False,
        notes="Baseline semantic retrieval.",
    ),
    RetrievalConfig(
        config_id="B",
        search_label="Hybrid",
        search_mode="hybrid",
        use_reranker=False,
        notes="Vector plus lexical search fused with RRF.",
    ),
    RetrievalConfig(
        config_id="C",
        search_label="Vector",
        search_mode="vector",
        use_reranker=True,
        notes="Wide vector recall followed by deterministic reranking.",
    ),
    RetrievalConfig(
        config_id="D",
        search_label="Hybrid",
        search_mode="hybrid",
        use_reranker=True,
        notes="Wide hybrid recall, RRF, then deterministic reranking.",
    ),
)


@dataclass(frozen=True)
class GoldenRetrievalCase:
    """One hand-annotated retrieval query."""

    query_id: str
    query: str
    intent: str
    relevant_budget_ids: tuple[str, ...]
    expected_component_ids: tuple[str, ...]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> GoldenRetrievalCase:
        query_id = str(payload.get("query_id", "")).strip()
        query = str(payload.get("query", "")).strip()
        intent = str(payload.get("intent", "")).strip()
        relevant_budget_ids = tuple(
            str(value).strip()
            for value in payload.get("relevant_budget_ids", [])
            if str(value).strip()
        )
        expected_component_ids = tuple(
            str(value).strip()
            for value in payload.get("expected_component_ids", [])
            if str(value).strip()
        )

        if not query_id:
            raise ValueError("query_id must not be empty")
        if not query:
            raise ValueError(f"{query_id}: query must not be empty")
        if not relevant_budget_ids:
            raise ValueError(f"{query_id}: relevant_budget_ids must not be empty")
        if not expected_component_ids:
            raise ValueError(f"{query_id}: expected_component_ids must not be empty")

        return cls(
            query_id=query_id,
            query=query,
            intent=intent,
            relevant_budget_ids=relevant_budget_ids,
            expected_component_ids=expected_component_ids,
        )


@dataclass(frozen=True)
class RetrievalCaseEvaluation:
    """Evaluation result for one case and one retrieval configuration."""

    config_id: str
    query_id: str
    query: str
    relevant_budget_ids: tuple[str, ...]
    expected_component_ids: tuple[str, ...]
    top_budget_ids: tuple[str, ...]
    top_component_ids: tuple[str, ...]
    result_count: int
    precision_at_k: float
    result_budget_precision_at_k: float
    unique_budget_precision_at_k: float
    budget_hit_at_k: bool
    component_hit_at_k: bool
    top1_budget_accuracy: bool
    top1_component_accuracy: bool
    best_budget_rank: int | None
    best_component_rank: int | None
    latency_ms: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["relevant_budget_ids"] = list(self.relevant_budget_ids)
        payload["expected_component_ids"] = list(self.expected_component_ids)
        payload["top_budget_ids"] = list(self.top_budget_ids)
        payload["top_component_ids"] = list(self.top_component_ids)
        return payload


def load_golden_cases(path: Path = DEFAULT_GOLDEN_PATH) -> list[GoldenRetrievalCase]:
    """Load Session 10 golden retrieval cases from JSON."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_queries = payload.get("queries")
    if not isinstance(raw_queries, list):
        raise ValueError(f"{path}: queries must be a list")

    cases = [
        GoldenRetrievalCase.from_dict(item)
        for item in raw_queries
        if isinstance(item, dict)
    ]
    if not cases:
        raise ValueError(f"{path}: no golden retrieval cases found")

    return cases


def evaluate_case(
    *,
    case: GoldenRetrievalCase,
    config_id: str,
    results: list[dict[str, Any]],
    latency_ms: int,
    k: int = DEFAULT_K,
) -> RetrievalCaseEvaluation:
    """Evaluate one query response using budget-level precision@k."""
    if k <= 0:
        raise ValueError("k must be positive")
    if latency_ms < 0:
        raise ValueError("latency_ms must be non-negative")

    top_results = results[:k]
    top_budget_ids = tuple(_extract_metadata_value(result, "budget_id") for result in top_results)
    top_component_ids = tuple(
        _extract_metadata_value(result, "component_id") for result in top_results
    )

    relevant_budget_set = set(case.relevant_budget_ids)
    expected_component_set = set(case.expected_component_ids)

    relevant_budget_hits = sum(
        1 for budget_id in top_budget_ids if budget_id in relevant_budget_set
    )
    result_budget_precision_at_k = round(relevant_budget_hits / k, 4)

    unique_retrieved_budget_ids = {
        budget_id for budget_id in top_budget_ids if budget_id
    }
    unique_budget_hits = len(unique_retrieved_budget_ids & relevant_budget_set)
    unique_budget_precision_at_k = round(unique_budget_hits / k, 4)

    best_budget_rank = _first_rank(top_budget_ids, relevant_budget_set)
    best_component_rank = _first_rank(top_component_ids, expected_component_set)

    top1_budget_accuracy = bool(top_budget_ids) and top_budget_ids[0] in relevant_budget_set
    top1_component_accuracy = (
        bool(top_component_ids) and top_component_ids[0] in expected_component_set
    )

    return RetrievalCaseEvaluation(
        config_id=config_id,
        query_id=case.query_id,
        query=case.query,
        relevant_budget_ids=case.relevant_budget_ids,
        expected_component_ids=case.expected_component_ids,
        top_budget_ids=top_budget_ids,
        top_component_ids=top_component_ids,
        result_count=len(results),
        precision_at_k=result_budget_precision_at_k,
        result_budget_precision_at_k=result_budget_precision_at_k,
        unique_budget_precision_at_k=unique_budget_precision_at_k,
        budget_hit_at_k=best_budget_rank is not None,
        component_hit_at_k=best_component_rank is not None,
        top1_budget_accuracy=top1_budget_accuracy,
        top1_component_accuracy=top1_component_accuracy,
        best_budget_rank=best_budget_rank,
        best_component_rank=best_component_rank,
        latency_ms=latency_ms,
    )


def summarize_variant_results(
    *,
    config_id: str,
    evaluations: list[RetrievalCaseEvaluation],
) -> dict[str, Any]:
    """Summarize one A/B/C/D variant."""
    if not evaluations:
        raise ValueError(f"{config_id}: evaluations must not be empty")

    return {
        "config_id": config_id,
        "case_count": len(evaluations),
        "mean_precision_at_5": round(
            sum(evaluation.precision_at_k for evaluation in evaluations)
            / len(evaluations),
            4,
        ),
        "mean_result_budget_precision_at_5": round(
            sum(evaluation.result_budget_precision_at_k for evaluation in evaluations)
            / len(evaluations),
            4,
        ),
        "mean_unique_budget_precision_at_5": round(
            sum(evaluation.unique_budget_precision_at_k for evaluation in evaluations)
            / len(evaluations),
            4,
        ),
        "budget_hit_rate_at_5": round(
            sum(1 for evaluation in evaluations if evaluation.budget_hit_at_k)
            / len(evaluations),
            4,
        ),
        "component_hit_rate_at_5": round(
            sum(1 for evaluation in evaluations if evaluation.component_hit_at_k)
            / len(evaluations),
            4,
        ),
        "top1_budget_accuracy": round(
            sum(1 for evaluation in evaluations if evaluation.top1_budget_accuracy)
            / len(evaluations),
            4,
        ),
        "top1_component_accuracy": round(
            sum(1 for evaluation in evaluations if evaluation.top1_component_accuracy)
            / len(evaluations),
            4,
        ),
        "mean_best_budget_rank": _mean_rank(
            [evaluation.best_budget_rank for evaluation in evaluations]
        ),
        "mean_best_component_rank": _mean_rank(
            [evaluation.best_component_rank for evaluation in evaluations]
        ),
        "median_latency_ms": int(median(evaluation.latency_ms for evaluation in evaluations)),
    }


def render_markdown_report(
    *,
    summaries: list[dict[str, Any]],
    evaluations: list[RetrievalCaseEvaluation],
    k: int = DEFAULT_K,
) -> str:
    """Render a markdown A/B/C/D retrieval report."""
    config_by_id = {config.config_id: config for config in RETRIEVAL_CONFIGS}
    lines = [
        "# Session 10 Retrieval A/B/C/D Evaluation",
        "",
        "This report compares retrieval configurations against the same golden set.",
        "",
        "Scope:",
        "",
        "- Metric focus: result-budget precision@5, unique-budget precision@5, hit@5, top-1 accuracy, and median latency.",
        "- Reranking in this branch uses the deterministic keyword-overlap reranker, not a live cross-encoder.",
        "- Results apply only to this small course corpus and golden set, now including challenge queries.",
        "",
        "## Comparison table",
        "",
        "| Config | Search | Reranking | result-budget precision@5 | unique-budget precision@5 | budget hit@5 | component hit@5 | top1 budget | top1 component | median latency ms |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]

    for summary in summaries:
        config = config_by_id[summary["config_id"]]
        lines.append(
            "| "
            f"{config.config_id} | "
            f"{config.search_label} | "
            f"{'Yes' if config.use_reranker else 'No'} | "
            f"{summary['mean_result_budget_precision_at_5']:.4f} | "
            f"{summary['mean_unique_budget_precision_at_5']:.4f} | "
            f"{summary['budget_hit_rate_at_5']:.4f} | "
            f"{summary['component_hit_rate_at_5']:.4f} | "
            f"{summary['top1_budget_accuracy']:.4f} | "
            f"{summary['top1_component_accuracy']:.4f} | "
            f"{summary['median_latency_ms']} |"
        )

    lines.extend(
        [
            "",
            "## Case details",
            "",
        ]
    )

    for evaluation in evaluations:
        lines.extend(
            [
                f"- `{evaluation.config_id}` / `{evaluation.query_id}`",
                f"  - query: {evaluation.query}",
                f"  - relevant budgets: {', '.join(evaluation.relevant_budget_ids)}",
                f"  - expected components: {', '.join(evaluation.expected_component_ids)}",
                f"  - top budgets: {', '.join(evaluation.top_budget_ids) or 'none'}",
                f"  - top components: {', '.join(evaluation.top_component_ids) or 'none'}",
                f"  - result-budget precision@{k}: {evaluation.result_budget_precision_at_k:.4f}",
                f"  - unique-budget precision@{k}: {evaluation.unique_budget_precision_at_k:.4f}",
                f"  - top1 budget accuracy: {evaluation.top1_budget_accuracy}",
                f"  - top1 component accuracy: {evaluation.top1_component_accuracy}",
                f"  - best budget rank: {evaluation.best_budget_rank or 'none'}",
                f"  - best component rank: {evaluation.best_component_rank or 'none'}",
                f"  - latency ms: {evaluation.latency_ms}",
            ]
        )

    lines.extend(
        [
            "",
            "## Limitations",
            "",
            "- The golden set is intentionally small but includes clean, ambiguous and low-signal challenge queries.",
            "- With one relevant budget per query, maximum unique-budget precision@5 is 0.2000.",
            "- Result-budget precision@5 may be higher because multiple chunks from the same relevant budget can appear in top 5.",
            "- Budget hit@5, component hit@5, and top-1 accuracy are included to make success easier to interpret.",
            "- The deterministic reranker is CI-safe and does not prove cross-encoder production latency.",
            "",
        ]
    )

    return "\n".join(lines)


def _extract_metadata_value(result: dict[str, Any], key: str) -> str:
    metadata = result.get("metadata", {})
    if not isinstance(metadata, dict):
        return ""
    value = metadata.get(key, "")
    return str(value).strip()


def _first_rank(values: tuple[str, ...], expected: set[str]) -> int | None:
    for rank, value in enumerate(values, start=1):
        if value in expected:
            return rank
    return None


def _mean_rank(values: list[int | None]) -> float | None:
    present_values = [value for value in values if value is not None]
    if not present_values:
        return None
    return round(sum(present_values) / len(present_values), 4)
