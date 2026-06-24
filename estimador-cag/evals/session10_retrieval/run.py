"""
Runtime Session 10 A/B/C/D retrieval measurement runner.

This runner executes the committed retrieval service against a deterministic
in-memory corpus built from data/budgets_sample.json. It avoids network calls,
PostgreSQL, FastAPI, OpenAI, DeepSeek, and Kimi while still exercising the
service-level vector, hybrid, and reranker branches.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import re
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.embedding_pipeline.reranker import KeywordOverlapReranker
from app.embedding_pipeline.search_service import (
    SearchQueryCommand,
    SearchResultItem,
    SemanticSearchService,
)
from app.persistence.repository import ChunkLexicalSearchResult, ChunkSearchResult
from evals.session10_retrieval.evaluator import (
    DEFAULT_GOLDEN_PATH,
    DEFAULT_K,
    RETRIEVAL_CONFIGS,
    evaluate_case,
    load_golden_cases,
    render_markdown_report,
    summarize_variant_results,
)

DEFAULT_BUDGETS_PATH = Path("data/budgets_sample.json")
DEFAULT_OUTPUT_PATH = Path("evals/session10_retrieval/results.json")
DEFAULT_REPORT_PATH = Path("evals/session10_retrieval/REPORT.md")
DEFAULT_RECALL_K = 20
EMBEDDING_DIMENSION = 1536

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


@dataclass(frozen=True)
class InMemoryChunk:
    """One component-level chunk used by the deterministic runner."""

    chunk_id: int
    document_id: int
    chunk_type: str
    content: str
    metadata: dict[str, Any]
    embedding: list[float]


class HashingVectorizer:
    """Deterministic token hashing vectorizer for offline retrieval measurement."""

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * EMBEDDING_DIMENSION
        for token in _tokenize(text):
            vector[_stable_bucket(token)] += 1.0

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]


class DeterministicEmbedder:
    """Query embedder compatible with SemanticSearchService."""

    def __init__(self, vectorizer: HashingVectorizer) -> None:
        self.vectorizer = vectorizer

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self.vectorizer.embed(text) for text in texts]


class InMemoryRetrievalRepository:
    """Repository adapter that mimics vector and lexical retrieval in memory."""

    def __init__(self, chunks: Sequence[InMemoryChunk]) -> None:
        self.chunks = list(chunks)

    async def search_chunks_by_embedding(
        self,
        *,
        query_embedding: list[float],
        k: int,
        metadata_filters: dict[str, Any] | None = None,
    ) -> list[ChunkSearchResult]:
        if k <= 0:
            raise ValueError("k must be positive")

        filtered_chunks = _filter_chunks(self.chunks, metadata_filters)
        ranked = sorted(
            filtered_chunks,
            key=lambda chunk: (
                _cosine_distance(query_embedding, chunk.embedding),
                chunk.chunk_id,
            ),
        )

        return [
            ChunkSearchResult(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                chunk_type=chunk.chunk_type,
                content=chunk.content,
                distance=_cosine_distance(query_embedding, chunk.embedding),
                metadata=chunk.metadata,
            )
            for chunk in ranked[:k]
        ]

    async def search_chunks_by_text(
        self,
        *,
        query_text: str,
        k: int,
        metadata_filters: dict[str, Any] | None = None,
    ) -> list[ChunkLexicalSearchResult]:
        if k <= 0:
            raise ValueError("k must be positive")

        query_terms = _tokenize(query_text)
        filtered_chunks = _filter_chunks(self.chunks, metadata_filters)

        scored = [
            (
                _lexical_score(query_terms, _tokenize(chunk.content)),
                chunk,
            )
            for chunk in filtered_chunks
        ]
        ranked = sorted(
            [item for item in scored if item[0] > 0],
            key=lambda item: (-item[0], item[1].chunk_id),
        )

        return [
            ChunkLexicalSearchResult(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                chunk_type=chunk.chunk_type,
                content=chunk.content,
                rank=score,
                metadata=chunk.metadata,
            )
            for score, chunk in ranked[:k]
        ]


def build_component_chunks(
    budgets_path: Path = DEFAULT_BUDGETS_PATH,
    *,
    vectorizer: HashingVectorizer | None = None,
) -> list[InMemoryChunk]:
    """Build one retrieval chunk per budget component."""
    vectorizer = vectorizer or HashingVectorizer()
    budgets = json.loads(budgets_path.read_text(encoding="utf-8"))

    chunks: list[InMemoryChunk] = []
    chunk_id = 1

    for document_id, budget in enumerate(budgets, start=1):
        client_metadata = budget["client_metadata"]
        for component in budget["components"]:
            content = _component_content(
                budget=budget,
                component=component,
            )
            metadata = {
                "budget_id": budget["budget_id"],
                "component_id": component["component_id"],
                "client_sector": client_metadata["sector"],
                "client_country": client_metadata["country"],
                "main_technology": budget["main_technology"],
                "year": budget["year"],
                "complexity": component["complexity"],
                "tech_stack": list(component["tech_stack"]),
                "scope": component["name"],
            }

            chunks.append(
                InMemoryChunk(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    chunk_type="budget_component",
                    content=content,
                    metadata=metadata,
                    embedding=vectorizer.embed(content),
                )
            )
            chunk_id += 1

    return chunks


def run_retrieval_measurement(
    *,
    golden_path: Path = DEFAULT_GOLDEN_PATH,
    budgets_path: Path = DEFAULT_BUDGETS_PATH,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    report_path: Path = DEFAULT_REPORT_PATH,
    k: int = DEFAULT_K,
    recall_k: int = DEFAULT_RECALL_K,
) -> dict[str, Any]:
    """Run deterministic A/B/C/D retrieval measurement and write artifacts."""
    if k <= 0:
        raise ValueError("k must be positive")
    if recall_k <= 0:
        raise ValueError("recall_k must be positive")

    cases = load_golden_cases(golden_path)
    vectorizer = HashingVectorizer()
    chunks = build_component_chunks(budgets_path, vectorizer=vectorizer)
    repository = InMemoryRetrievalRepository(chunks)
    service = SemanticSearchService(
        embedder=DeterministicEmbedder(vectorizer),
        repository=repository,
        reranker=KeywordOverlapReranker(),
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
        "case_count": len(cases),
        "chunk_count": len(chunks),
        "summaries": summaries,
        "evaluations": [evaluation.as_dict() for evaluation in evaluations],
    }

    _write_json(output_path, payload)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        render_markdown_report(
            summaries=summaries,
            evaluations=evaluations,
            k=k,
        ),
        encoding="utf-8",
    )

    return payload


def _component_content(*, budget: dict[str, Any], component: dict[str, Any]) -> str:
    dependencies = component.get("dependencies", [])
    return "\n".join(
        [
            f"Budget ID: {budget['budget_id']}",
            f"Client sector: {budget['client_metadata']['sector']}",
            f"Client country: {budget['client_metadata']['country']}",
            f"Project summary: {budget['project_summary']}",
            f"Main technology: {budget['main_technology']}",
            f"Component ID: {component['component_id']}",
            f"Component name: {component['name']}",
            f"Component description: {component['description']}",
            f"Tech stack: {', '.join(component['tech_stack'])}",
            f"Complexity: {component['complexity']}",
            f"Dependencies: {', '.join(dependencies) if dependencies else 'none'}",
        ]
    )


def _search_item_as_response_dict(item: SearchResultItem) -> dict[str, Any]:
    return {
        "chunk_id": item.chunk_id,
        "document_id": item.document_id,
        "chunk_type": item.chunk_type,
        "content": item.content,
        "distance": item.distance,
        "metadata": item.metadata,
    }


def _tokenize(text: str) -> set[str]:
    return {match.group(0).lower() for match in _TOKEN_RE.finditer(text)}


def _stable_bucket(token: str) -> int:
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, byteorder="big") % EMBEDDING_DIMENSION




def _cosine_distance(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 1.0
    dot = sum(a * b for a, b in zip(left, right, strict=False))
    return 1.0 - dot


def _lexical_score(query_terms: set[str], content_terms: set[str]) -> float:
    if not query_terms:
        return 0.0
    return len(query_terms & content_terms) / len(query_terms)


def _filter_chunks(
    chunks: Sequence[InMemoryChunk],
    metadata_filters: dict[str, Any] | None,
) -> list[InMemoryChunk]:
    if not metadata_filters:
        return list(chunks)

    filtered = []
    for chunk in chunks:
        if all(_metadata_matches(chunk.metadata, key, value) for key, value in metadata_filters.items()):
            filtered.append(chunk)

    return filtered


def _metadata_matches(metadata: dict[str, Any], key: str, expected: Any) -> bool:
    actual = metadata.get(key)
    if isinstance(expected, list):
        if isinstance(actual, list):
            return all(value in actual for value in expected)
        return False
    return actual == expected


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = Path(str(path) + ".tmp")
    tmp_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run deterministic Session 10 A/B/C/D retrieval measurement."
    )
    parser.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN_PATH)
    parser.add_argument("--budgets", type=Path, default=DEFAULT_BUDGETS_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--k", type=int, default=DEFAULT_K)
    parser.add_argument("--recall-k", type=int, default=DEFAULT_RECALL_K)
    args = parser.parse_args(argv)

    payload = run_retrieval_measurement(
        golden_path=args.golden,
        budgets_path=args.budgets,
        output_path=args.output,
        report_path=args.report,
        k=args.k,
        recall_k=args.recall_k,
    )

    print(f"Wrote retrieval results: {args.output}")
    print(f"Wrote retrieval report: {args.report}")
    print(json.dumps(payload["summaries"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
