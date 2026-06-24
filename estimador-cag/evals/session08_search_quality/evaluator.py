"""
Offline Session 08 search-quality evaluator.

This module evaluates already-captured /search response payloads. It deliberately
does not call FastAPI, PostgreSQL, OpenAI, DeepSeek, or Kimi. Its job is to make
retrieval quality measurable before changing retrieval behavior.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

DEFAULT_CASES_PATH = Path(__file__).with_name("cases.jsonl")


@dataclass(frozen=True)
class SearchQualityCase:
    """One expected retrieval behavior for a Session 08 query."""

    case_id: str
    query: str
    expected_component_ids: tuple[str, ...]
    answerable: bool = True
    notes: str = ""

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> SearchQualityCase:
        case_id = str(payload.get("case_id", "")).strip()
        query = str(payload.get("query", "")).strip()
        expected_component_ids = tuple(
            str(component_id).strip()
            for component_id in payload.get("expected_component_ids", [])
            if str(component_id).strip()
        )
        answerable = bool(payload.get("answerable", True))
        notes = str(payload.get("notes", "")).strip()

        if not case_id:
            raise ValueError("case_id must not be empty")
        if not query:
            raise ValueError(f"{case_id}: query must not be empty")
        if answerable and not expected_component_ids:
            raise ValueError(
                f"{case_id}: answerable cases require at least one expected component id"
            )

        return cls(
            case_id=case_id,
            query=query,
            expected_component_ids=expected_component_ids,
            answerable=answerable,
            notes=notes,
        )


@dataclass(frozen=True)
class CaseEvaluation:
    """Deterministic evaluation result for one search-quality case."""

    case_id: str
    query: str
    answerable: bool
    expected_component_ids: tuple[str, ...]
    result_count: int
    nearest_component_id: str | None
    nearest_distance: float | None
    best_expected_rank: int | None
    top_k_hit: bool
    out_of_domain_returned_results: bool
    quality_label: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["expected_component_ids"] = list(self.expected_component_ids)
        return payload


def load_cases(path: Path = DEFAULT_CASES_PATH) -> list[SearchQualityCase]:
    """Load JSONL search-quality cases."""
    cases: list[SearchQualityCase] = []

    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number}: invalid JSONL: {exc}") from exc

        cases.append(SearchQualityCase.from_dict(payload))

    if not cases:
        raise ValueError(f"{path}: no cases found")

    return cases


def evaluate_response(
    case: SearchQualityCase,
    response: dict[str, Any],
) -> CaseEvaluation:
    """Evaluate one /search response payload against one expected case."""
    raw_results = response.get("results", [])
    if not isinstance(raw_results, list):
        raise ValueError(f"{case.case_id}: response.results must be a list")

    nearest_component_id: str | None = None
    nearest_distance: float | None = None
    best_expected_rank: int | None = None

    for rank, result in enumerate(raw_results, start=1):
        if not isinstance(result, dict):
            continue

        component_id = _extract_component_id(result)
        distance = _extract_distance(result)

        if rank == 1:
            nearest_component_id = component_id
            nearest_distance = distance

        if (
            case.answerable
            and component_id in case.expected_component_ids
            and best_expected_rank is None
        ):
            best_expected_rank = rank

    top_k_hit = case.answerable and best_expected_rank is not None
    out_of_domain_returned_results = (not case.answerable) and bool(raw_results)

    return CaseEvaluation(
        case_id=case.case_id,
        query=case.query,
        answerable=case.answerable,
        expected_component_ids=case.expected_component_ids,
        result_count=len(raw_results),
        nearest_component_id=nearest_component_id,
        nearest_distance=nearest_distance,
        best_expected_rank=best_expected_rank,
        top_k_hit=top_k_hit,
        out_of_domain_returned_results=out_of_domain_returned_results,
        quality_label=_quality_label(
            answerable=case.answerable,
            top_k_hit=top_k_hit,
            out_of_domain_returned_results=out_of_domain_returned_results,
        ),
    )


def summarize_evaluations(evaluations: list[CaseEvaluation]) -> dict[str, Any]:
    """Return aggregate metrics for a deterministic evaluation run."""
    answerable = [evaluation for evaluation in evaluations if evaluation.answerable]
    negative_controls = [
        evaluation for evaluation in evaluations if not evaluation.answerable
    ]
    answerable_hits = sum(1 for evaluation in answerable if evaluation.top_k_hit)
    ranks = [
        evaluation.best_expected_rank
        for evaluation in answerable
        if evaluation.best_expected_rank is not None
    ]

    return {
        "case_count": len(evaluations),
        "answerable_case_count": len(answerable),
        "answerable_top_k_hits": answerable_hits,
        "answerable_top_k_hit_rate": (
            answerable_hits / len(answerable) if answerable else None
        ),
        "mean_best_expected_rank": (sum(ranks) / len(ranks) if ranks else None),
        "negative_control_count": len(negative_controls),
        "negative_controls_returning_results": sum(
            1 for evaluation in negative_controls if evaluation.out_of_domain_returned_results
        ),
    }


def render_markdown_report(
    *,
    summary: dict[str, Any],
    evaluations: list[CaseEvaluation],
) -> str:
    """Render a small human-readable markdown report."""
    lines = [
        "# Session 08 Search Quality Evaluation",
        "",
        "This is an offline evaluator for the Session 08 live-inspired hardening branch.",
        "",
        "Scope:",
        "",
        "- No LLM judge.",
        "- No live provider call.",
        "- No PostgreSQL or FastAPI call.",
        "- Evaluates captured `/search` response payloads only.",
        "- This is not a Task 09 implementation claim.",
        "- This does not claim benchmark superiority.",
        "",
        "Summary:",
        "",
        f"- Cases: {summary['case_count']}",
        f"- Answerable cases: {summary['answerable_case_count']}",
        f"- Answerable top-k hits: {summary['answerable_top_k_hits']}",
        f"- Answerable top-k hit rate: {_format_optional_float(summary['answerable_top_k_hit_rate'])}",
        f"- Mean best expected rank: {_format_optional_float(summary['mean_best_expected_rank'])}",
        f"- Negative controls: {summary['negative_control_count']}",
        f"- Negative controls returning results: {summary['negative_controls_returning_results']}",
        "",
        "Case results:",
        "",
    ]

    for evaluation in evaluations:
        lines.extend(
            [
                f"- `{evaluation.case_id}`: {evaluation.quality_label}",
                f"  - query: {evaluation.query}",
                f"  - expected: {', '.join(evaluation.expected_component_ids) or 'none'}",
                f"  - nearest_component_id: {evaluation.nearest_component_id or 'none'}",
                f"  - nearest_distance: {_format_optional_float(evaluation.nearest_distance)}",
                f"  - best_expected_rank: {evaluation.best_expected_rank or 'none'}",
                f"  - result_count: {evaluation.result_count}",
            ]
        )

    lines.extend(
        [
            "",
            "Interpretation:",
            "",
            "The negative-control case intentionally records the current nearest-neighbor behavior.",
            "A later slice may add confidence labeling or a maximum-distance threshold, but this evaluator only measures the current behavior.",
            "",
        ]
    )

    return "\n".join(lines)


def evaluate_response_map(
    *,
    cases: list[SearchQualityCase],
    responses_by_case_id: dict[str, dict[str, Any]],
) -> list[CaseEvaluation]:
    """Evaluate a mapping of case_id to captured /search response payload."""
    evaluations: list[CaseEvaluation] = []

    for case in cases:
        if case.case_id not in responses_by_case_id:
            raise ValueError(f"Missing response for case_id={case.case_id}")
        evaluations.append(evaluate_response(case, responses_by_case_id[case.case_id]))

    return evaluations


def _extract_component_id(result: dict[str, Any]) -> str | None:
    metadata = result.get("metadata", {})
    if not isinstance(metadata, dict):
        return None

    component_id = metadata.get("component_id")
    if component_id is None:
        return None

    stripped = str(component_id).strip()
    return stripped or None


def _extract_distance(result: dict[str, Any]) -> float | None:
    raw_distance = result.get("distance")
    if raw_distance is None:
        return None

    try:
        return float(raw_distance)
    except (TypeError, ValueError):
        return None


def _quality_label(
    *,
    answerable: bool,
    top_k_hit: bool,
    out_of_domain_returned_results: bool,
) -> str:
    if answerable and top_k_hit:
        return "pass"
    if answerable:
        return "miss"
    if out_of_domain_returned_results:
        return "negative_control_nearest_neighbor"
    return "negative_control_empty"


def _format_optional_float(value: float | None) -> str:
    if value is None:
        return "none"
    return f"{value:.4f}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate captured Session 08 /search responses."
    )
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument(
        "--responses",
        type=Path,
        required=True,
        help="JSON file mapping case_id to captured /search response payload.",
    )
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    cases = load_cases(args.cases)
    responses_by_case_id = json.loads(args.responses.read_text(encoding="utf-8"))
    if not isinstance(responses_by_case_id, dict):
        raise ValueError("--responses must be a JSON object keyed by case_id")

    evaluations = evaluate_response_map(
        cases=cases,
        responses_by_case_id=responses_by_case_id,
    )
    summary = summarize_evaluations(evaluations)

    output = {
        "summary": summary,
        "evaluations": [evaluation.as_dict() for evaluation in evaluations],
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))

    if args.report:
        args.report.write_text(
            render_markdown_report(summary=summary, evaluations=evaluations),
            encoding="utf-8",
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
