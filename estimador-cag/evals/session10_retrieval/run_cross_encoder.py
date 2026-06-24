"""Manual Session 10 A/B/C/D runner using a real cross-encoder reranker.

Normal CI uses the deterministic keyword reranker. This script is for manual
local evidence when sentence-transformers can download/load the model.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from app.embedding_pipeline.reranker import DEFAULT_CROSS_ENCODER_MODEL, CrossEncoderReranker
from app.embedding_pipeline.search_service import SearchQueryCommand, SearchResultItem, SemanticSearchService
from evals.session10_retrieval.evaluator import (
    DEFAULT_GOLDEN_PATH,
    DEFAULT_K,
    RETRIEVAL_CONFIGS,
    evaluate_case,
    load_golden_cases,
    render_markdown_report,
    summarize_variant_results,
)
from evals.session10_retrieval.run import (
    DEFAULT_BUDGETS_PATH,
    DEFAULT_RECALL_K,
    DeterministicEmbedder,
    HashingVectorizer,
    InMemoryRetrievalRepository,
    build_component_chunks,
)

DEFAULT_OUTPUT_PATH = Path("evals/session10_retrieval/results_cross_encoder.local.json")
DEFAULT_REPORT_PATH = Path("evals/session10_retrieval/REPORT_CROSS_ENCODER.local.md")


def run_cross_encoder_measurement(
    *,
    golden_path: Path = DEFAULT_GOLDEN_PATH,
    budgets_path: Path = DEFAULT_BUDGETS_PATH,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    report_path: Path = DEFAULT_REPORT_PATH,
    k: int = DEFAULT_K,
    recall_k: int = DEFAULT_RECALL_K,
    model_name: str = DEFAULT_CROSS_ENCODER_MODEL,
    device: str | None = None,
) -> dict[str, Any]:
    """Run A/B/C/D with real cross-encoder reranking for variants C and D."""
    cases = load_golden_cases(golden_path)
    vectorizer = HashingVectorizer()
    chunks = build_component_chunks(budgets_path, vectorizer=vectorizer)
    repository = InMemoryRetrievalRepository(chunks)
    service = SemanticSearchService(
        embedder=DeterministicEmbedder(vectorizer),
        repository=repository,
        reranker=CrossEncoderReranker(model_name=model_name, device=device),
    )

    evaluations = []
    for config in RETRIEVAL_CONFIGS:
        for case in cases:
            started = time.perf_counter()
            result = asyncio.run(
                service.search(
                    SearchQueryCommand(
                        query=case.query,
                        k=k,
                        search_mode=config.search_mode,
                        recall_k=recall_k,
                        use_reranker=config.use_reranker,
                        rerank_top_n=k,
                    )
                )
            )
            latency_ms = int((time.perf_counter() - started) * 1000)
            evaluations.append(
                evaluate_case(
                    case=case,
                    config_id=config.config_id,
                    results=[_search_item_as_response_dict(item) for item in result.results],
                    latency_ms=latency_ms,
                    k=k,
                )
            )

    summaries = [
        summarize_variant_results(
            config_id=config.config_id,
            evaluations=[
                evaluation
                for evaluation in evaluations
                if evaluation.config_id == config.config_id
            ],
        )
        for config in RETRIEVAL_CONFIGS
    ]
    payload = {
        "k": k,
        "recall_k": recall_k,
        "reranker_mode": "cross-encoder",
        "cross_encoder_model": model_name,
        "case_count": len(cases),
        "chunk_count": len(chunks),
        "summaries": summaries,
        "evaluations": [evaluation.as_dict() for evaluation in evaluations],
    }

    _write_json(output_path, payload)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        render_markdown_report(summaries=summaries, evaluations=evaluations, k=k),
        encoding="utf-8",
    )
    return payload


def _search_item_as_response_dict(item: SearchResultItem) -> dict[str, Any]:
    return {
        "chunk_id": item.chunk_id,
        "document_id": item.document_id,
        "chunk_type": item.chunk_type,
        "content": item.content,
        "distance": item.distance,
        "metadata": item.metadata,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN_PATH)
    parser.add_argument("--budgets", type=Path, default=DEFAULT_BUDGETS_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--k", type=int, default=DEFAULT_K)
    parser.add_argument("--recall-k", type=int, default=DEFAULT_RECALL_K)
    parser.add_argument("--model", default=DEFAULT_CROSS_ENCODER_MODEL)
    parser.add_argument("--device", default=None)
    args = parser.parse_args(argv)

    payload = run_cross_encoder_measurement(
        golden_path=args.golden,
        budgets_path=args.budgets,
        output_path=args.output,
        report_path=args.report,
        k=args.k,
        recall_k=args.recall_k,
        model_name=args.model,
        device=args.device,
    )
    print(f"Wrote cross-encoder retrieval results: {args.output}")
    print(f"Wrote cross-encoder retrieval report: {args.report}")
    print(json.dumps(payload["summaries"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
