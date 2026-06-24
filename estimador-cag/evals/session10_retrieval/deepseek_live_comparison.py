"""
Optional DeepSeek live comparison for Session 10 retrieval.

This module is intentionally not part of normal CI as a live provider call.
By default it writes a dry-run payload with the exact baseline and
retrieval-grounded prompts. It calls DeepSeek only when --live is passed
and DEEPSEEK_API_KEY is available.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any

from openai import OpenAI

from app.embedding_pipeline.reranker import KeywordOverlapReranker
from app.embedding_pipeline.search_service import (
    SearchQueryCommand,
    SearchResultItem,
    SemanticSearchService,
)
from evals.session10_retrieval.evaluator import (
    DEFAULT_GOLDEN_PATH,
    GoldenRetrievalCase,
    load_golden_cases,
)
from evals.session10_retrieval.run import (
    DEFAULT_BUDGETS_PATH,
    DeterministicEmbedder,
    HashingVectorizer,
    InMemoryRetrievalRepository,
    build_component_chunks,
)

DEFAULT_OUTPUT_PATH = Path("evals/session10_retrieval/deepseek_live_comparison.local.json")
DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MAX_CASES = 3


class DeepSeekLiveComparisonError(RuntimeError):
    """Raised when the optional live comparison cannot run safely."""


def select_cases(
    *,
    golden_path: Path = DEFAULT_GOLDEN_PATH,
    query_ids: list[str] | None = None,
    max_cases: int = DEFAULT_MAX_CASES,
) -> list[GoldenRetrievalCase]:
    """Select a small deterministic case subset for bounded live comparison."""
    cases = load_golden_cases(golden_path)

    if query_ids:
        selected = [case for case in cases if case.query_id in set(query_ids)]
    else:
        selected = cases[:max_cases]

    if not selected:
        raise DeepSeekLiveComparisonError("No golden cases selected for live comparison.")

    return selected[:max_cases]


def build_retrieval_service(
    *,
    budgets_path: Path = DEFAULT_BUDGETS_PATH,
) -> SemanticSearchService:
    """Build the same deterministic retrieval service used by the A/B/C/D runner."""
    vectorizer = HashingVectorizer()
    chunks = build_component_chunks(budgets_path, vectorizer=vectorizer)
    repository = InMemoryRetrievalRepository(chunks)

    return SemanticSearchService(
        embedder=DeterministicEmbedder(vectorizer),
        repository=repository,
        reranker=KeywordOverlapReranker(),
    )


def retrieve_context(
    service: SemanticSearchService,
    case: GoldenRetrievalCase,
    *,
    k: int,
    recall_k: int,
) -> list[SearchResultItem]:
    """Retrieve context using configuration D semantics: hybrid plus reranking."""
    result = asyncio.run(
        service.search(
            SearchQueryCommand(
                query=case.query,
                k=k,
                search_mode="hybrid",
                recall_k=recall_k,
                use_reranker=True,
                rerank_top_n=k,
            )
        )
    )
    return list(result.results)


def search_items_as_context(items: list[SearchResultItem]) -> list[dict[str, Any]]:
    """Convert retrieval results into compact prompt context."""
    contexts = []
    for rank, item in enumerate(items, start=1):
        metadata = dict(item.metadata)
        contexts.append(
            {
                "rank": rank,
                "budget_id": metadata.get("budget_id"),
                "component_id": metadata.get("component_id"),
                "client_sector": metadata.get("client_sector"),
                "main_technology": metadata.get("main_technology"),
                "distance": item.distance,
                "content": item.content,
            }
        )
    return contexts


def build_baseline_messages(case: GoldenRetrievalCase) -> list[dict[str, str]]:
    """Build a DeepSeek-only baseline prompt without retrieval context."""
    return [
        {
            "role": "system",
            "content": (
                "You are evaluating a software estimation retrieval benchmark. "
                "Return strict JSON only. Do not use markdown."
            ),
        },
        {
            "role": "user",
            "content": (
                "Answer this query without retrieved project context. "
                "Return JSON with keys: selected_budget_ids, selected_component_ids, "
                "answer, uncertainty, and evidence_notes. "
                f"Query: {case.query}"
            ),
        },
    ]


def build_retrieval_messages(
    case: GoldenRetrievalCase,
    contexts: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Build a retrieval-grounded prompt with explicit evidence constraints."""
    context_text = json.dumps(contexts, indent=2, ensure_ascii=False)

    return [
        {
            "role": "system",
            "content": (
                "You are evaluating a software estimation retrieval benchmark. "
                "Use only the retrieved context when selecting budget and component IDs. "
                "Return strict JSON only. Do not use markdown."
            ),
        },
        {
            "role": "user",
            "content": (
                "Given the user query and retrieved context, identify the best matching "
                "budget and component references. Return JSON with keys: "
                "selected_budget_ids, selected_component_ids, answer, uncertainty, "
                "and evidence_notes. "
                f"Query: {case.query}\n"
                f"Retrieved context: {context_text}"
            ),
        },
    ]


def call_deepseek(
    *,
    messages: list[dict[str, str]],
    api_key: str,
    model: str,
    base_url: str,
) -> dict[str, Any]:
    """Call DeepSeek through the OpenAI-compatible SDK."""
    client = OpenAI(api_key=api_key, base_url=base_url)
    started = time.perf_counter()

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        stream=False,
    )

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    message = response.choices[0].message

    return {
        "content": message.content,
        "latency_ms": elapsed_ms,
        "model": model,
        "usage": _usage_as_dict(getattr(response, "usage", None)),
    }


def run_comparison(
    *,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    golden_path: Path = DEFAULT_GOLDEN_PATH,
    budgets_path: Path = DEFAULT_BUDGETS_PATH,
    query_ids: list[str] | None = None,
    max_cases: int = DEFAULT_MAX_CASES,
    k: int = 5,
    recall_k: int = 8,
    live: bool = False,
    model: str | None = None,
    base_url: str | None = None,
) -> dict[str, Any]:
    """Run a bounded DeepSeek baseline versus retrieval-grounded comparison."""
    resolved_model = model or os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL)
    resolved_base_url = base_url or os.getenv("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL)
    api_key = os.getenv("DEEPSEEK_API_KEY")

    if live and not api_key:
        raise DeepSeekLiveComparisonError("DEEPSEEK_API_KEY is required when --live is used.")

    service = build_retrieval_service(budgets_path=budgets_path)
    records = []

    for case in select_cases(golden_path=golden_path, query_ids=query_ids, max_cases=max_cases):
        contexts = search_items_as_context(
            retrieve_context(service, case, k=k, recall_k=recall_k)
        )
        baseline_messages = build_baseline_messages(case)
        retrieval_messages = build_retrieval_messages(case, contexts)

        record: dict[str, Any] = {
            "query_id": case.query_id,
            "query": case.query,
            "expected_budget_ids": list(case.relevant_budget_ids),
            "expected_component_ids": list(case.expected_component_ids),
            "retrieved_context": contexts,
        }

        if live:
            record["baseline_response"] = call_deepseek(
                messages=baseline_messages,
                api_key=api_key or "",
                model=resolved_model,
                base_url=resolved_base_url,
            )
            record["retrieval_grounded_response"] = call_deepseek(
                messages=retrieval_messages,
                api_key=api_key or "",
                model=resolved_model,
                base_url=resolved_base_url,
            )
        else:
            record["baseline_prompt"] = baseline_messages
            record["retrieval_grounded_prompt"] = retrieval_messages

        records.append(record)

    payload = {
        "provider": "deepseek",
        "mode": "live" if live else "dry_run",
        "model": resolved_model,
        "base_url": resolved_base_url,
        "k": k,
        "recall_k": recall_k,
        "case_count": len(records),
        "records": records,
        "notes": [
            "Dry-run mode makes no network calls.",
            "Live mode is opt-in and intentionally excluded from normal CI.",
            "The retrieval-grounded prompt uses Session 10 hybrid plus reranking semantics.",
        ],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def _usage_as_dict(usage: Any) -> dict[str, Any] | None:
    if usage is None:
        return None
    if hasattr(usage, "model_dump"):
        return usage.model_dump()
    if isinstance(usage, dict):
        return usage
    return None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN_PATH)
    parser.add_argument("--budgets", type=Path, default=DEFAULT_BUDGETS_PATH)
    parser.add_argument("--query-id", action="append", default=None)
    parser.add_argument("--max-cases", type=int, default=DEFAULT_MAX_CASES)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--recall-k", type=int, default=8)
    parser.add_argument("--model", default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--live", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    payload = run_comparison(
        output_path=args.output,
        golden_path=args.golden,
        budgets_path=args.budgets,
        query_ids=args.query_id,
        max_cases=args.max_cases,
        k=args.k,
        recall_k=args.recall_k,
        live=args.live,
        model=args.model,
        base_url=args.base_url,
    )
    print(f"Wrote DeepSeek comparison payload: {args.output}")
    print(json.dumps({key: payload[key] for key in ["provider", "mode", "model", "case_count"]}, indent=2))


if __name__ == "__main__":
    main()
