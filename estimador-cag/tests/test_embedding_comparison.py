from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.embedding_pipeline.chunker import JSONStructuralChunker
from app.embedding_pipeline.comparison import (
    ChunkingComparisonService,
    ChunkingQueryComparisonService,
    WholeBudgetChunker,
    cosine_similarity,
)
from app.embedding_pipeline.schemas import Budget


def load_sample_budgets() -> list[Budget]:
    payload = json.loads(Path("data/budgets_sample.json").read_text(encoding="utf-8"))
    return [Budget.model_validate(item) for item in payload]


def test_whole_budget_chunker_creates_one_chunk_per_budget() -> None:
    budgets = load_sample_budgets()

    chunks = WholeBudgetChunker().chunk(budgets)

    assert len(chunks) == len(budgets)
    assert all(chunk.token_count > 0 for chunk in chunks)
    assert chunks[0].chunk_id == f"{budgets[0].budget_id}::whole_budget"
    assert chunks[0].metadata["chunking_strategy"] == "whole_budget"
    assert chunks[0].metadata["budget_id"] == budgets[0].budget_id
    assert chunks[0].metadata["component_count"] == len(budgets[0].components)
    assert "Full budget:" in chunks[0].text
    assert "Components:" in chunks[0].text
    assert budgets[0].components[0].name in chunks[0].text


def test_comparison_service_reports_structural_against_whole_budget_baseline() -> None:
    budgets = load_sample_budgets()

    comparison = ChunkingComparisonService(
        strategies={
            "structural_component": JSONStructuralChunker(),
            "whole_budget": WholeBudgetChunker(),
        }
    ).compare(budgets)

    by_name = {summary.strategy_name: summary for summary in comparison.strategies}

    structural = by_name["structural_component"]
    whole_budget = by_name["whole_budget"]

    expected_component_count = sum(len(budget.components) for budget in budgets)

    assert structural.total_chunks == expected_component_count
    assert whole_budget.total_chunks == len(budgets)

    assert structural.total_tokens > 0
    assert whole_budget.total_tokens > 0

    assert structural.average_tokens == pytest.approx(
        structural.total_tokens / structural.total_chunks
    )
    assert whole_budget.average_tokens == pytest.approx(
        whole_budget.total_tokens / whole_budget.total_chunks
    )

    assert structural.min_tokens <= structural.max_tokens
    assert whole_budget.min_tokens <= whole_budget.max_tokens

    assert len(structural.chunk_ids) == structural.total_chunks
    assert len(whole_budget.chunk_ids) == whole_budget.total_chunks


def test_default_comparison_service_includes_structural_and_whole_budget_strategies() -> None:
    budgets = load_sample_budgets()

    comparison = ChunkingComparisonService().compare(budgets)

    strategy_names = [summary.strategy_name for summary in comparison.strategies]

    assert strategy_names == ["structural_component", "whole_budget"]


class KeywordTextEmbedder:
    """Deterministic fake embedder for query ranking tests."""

    keywords = [
        "oauth",
        "jwt",
        "authorization",
        "token",
        "authentication",
        "banking",
        "inventory",
        "checkout",
        "telemetry",
        "dashboard",
        "patient",
        "document",
    ]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []

        for text in texts:
            lower_text = text.lower()
            vectors.append(
                [float(lower_text.count(keyword)) for keyword in self.keywords]
            )

        return vectors


def test_cosine_similarity_handles_identical_orthogonal_and_zero_vectors() -> None:
    assert cosine_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == pytest.approx(0.0)


def test_query_comparison_ranks_matching_authentication_chunks_per_strategy() -> None:
    budgets = load_sample_budgets()

    comparison = ChunkingQueryComparisonService(
        text_embedder=KeywordTextEmbedder()
    ).compare_query(
        budgets=budgets,
        query="OAuth JWT authentication token banking authorization",
        top_k=2,
    )

    by_name = {strategy.strategy_name: strategy for strategy in comparison.strategies}

    structural_top = by_name["structural_component"].top_chunks[0]
    whole_budget_top = by_name["whole_budget"].top_chunks[0]

    assert comparison.query == "OAuth JWT authentication token banking authorization"
    assert comparison.top_k == 2

    assert structural_top.rank == 1
    assert structural_top.chunk_id == "BUD-2024-014::AUTH-001"
    assert structural_top.metadata["component_id"] == "AUTH-001"
    assert structural_top.score > 0

    assert whole_budget_top.rank == 1
    assert whole_budget_top.chunk_id == "BUD-2024-014::whole_budget"
    assert whole_budget_top.metadata["budget_id"] == "BUD-2024-014"
    assert whole_budget_top.score > 0

    assert len(by_name["structural_component"].top_chunks) == 2
    assert len(by_name["whole_budget"].top_chunks) == 2


def test_query_comparison_rejects_non_positive_top_k() -> None:
    budgets = load_sample_budgets()

    service = ChunkingQueryComparisonService(text_embedder=KeywordTextEmbedder())

    with pytest.raises(ValueError, match="top_k"):
        service.compare_query(budgets=budgets, query="OAuth", top_k=0)
