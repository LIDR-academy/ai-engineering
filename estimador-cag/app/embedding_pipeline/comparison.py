"""
LAYER: embedding_pipeline comparison
RESPONSIBILITY: Compare chunking strategies over the same budget corpus.
WHY IT EXISTS: Session 07 live focuses on learning how chunking strategy changes
               chunk counts, token distribution, and future retrieval behavior.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Protocol

from pydantic import BaseModel, Field

from app.embedding_pipeline.chunker import JSONStructuralChunker, _encoding_for_embedding_model
from app.embedding_pipeline.schemas import Budget, Chunk, MetadataValue


class BudgetChunker(Protocol):
    """Small protocol shared by chunking strategies used in comparisons."""

    def chunk(self, budgets: list[Budget]) -> list[Chunk]:
        """Return chunks for the supplied budgets."""


class TextEmbedder(Protocol):
    """Small protocol for deterministic or live text embedding providers."""

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text."""


class WholeBudgetChunker:
    """
    Deliberately broad baseline: one whole budget becomes one chunk.

    This strategy is useful for learning because it shows the opposite of the
    structural component baseline. It should usually be worse for retrieval
    because unrelated components are blended into one vector.
    """

    strategy_name = "whole_budget"

    def __init__(self) -> None:
        self._encoding = _encoding_for_embedding_model()

    def chunk(self, budgets: list[Budget]) -> list[Chunk]:
        """Create one broad chunk per budget."""
        chunks: list[Chunk] = []

        for budget in budgets:
            text = self._build_budget_text(budget)
            chunks.append(
                Chunk(
                    chunk_id=f"{budget.budget_id}::whole_budget",
                    text=text,
                    metadata={
                        "chunking_strategy": self.strategy_name,
                        "budget_id": budget.budget_id,
                        "client_name": budget.client_metadata.name,
                        "client_sector": budget.client_metadata.sector,
                        "client_country": budget.client_metadata.country,
                        "main_technology": budget.main_technology,
                        "year": budget.year,
                        "total_estimated_hours": budget.total_estimated_hours,
                        "component_count": len(budget.components),
                        "component_ids": [
                            component.component_id for component in budget.components
                        ],
                    },
                    token_count=len(self._encoding.encode(text)),
                )
            )

        return chunks

    def _build_budget_text(self, budget: Budget) -> str:
        component_lines = []

        for component in budget.components:
            dependencies = ", ".join(component.dependencies) if component.dependencies else "none"
            component_lines.append(
                "\n".join(
                    [
                        f"- Component: {component.name}",
                        f"  Description: {component.description}",
                        f"  Tech stack: {', '.join(component.tech_stack)}",
                        f"  Complexity: {component.complexity}",
                        f"  Estimated hours: {component.estimated_hours}",
                        f"  Dependencies: {dependencies}",
                    ]
                )
            )

        return "\n".join(
            [
                f"Full budget: {budget.budget_id}",
                f"Project: {budget.project_summary}",
                (
                    f"Client sector: {budget.client_metadata.sector} | "
                    f"Country: {budget.client_metadata.country} | "
                    f"Year: {budget.year}"
                ),
                f"Main technology: {budget.main_technology}",
                f"Total estimated hours: {budget.total_estimated_hours}",
                "",
                "Components:",
                *component_lines,
            ]
        )


class ChunkingStrategySummary(BaseModel):
    """Aggregate stats for one chunking strategy."""

    strategy_name: str = Field(min_length=1)
    total_chunks: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    min_tokens: int = Field(ge=0)
    max_tokens: int = Field(ge=0)
    average_tokens: float = Field(ge=0)
    chunk_ids: list[str]


class ChunkingComparison(BaseModel):
    """Comparison result across multiple chunking strategies."""

    strategies: list[ChunkingStrategySummary] = Field(min_length=1)


class RankedChunk(BaseModel):
    """One ranked chunk for a query within one strategy result."""

    rank: int = Field(ge=1)
    chunk_id: str = Field(min_length=1)
    score: float
    text_preview: str = Field(min_length=1)
    metadata: dict[str, MetadataValue]


class QueryStrategyRanking(BaseModel):
    """Top-k ranking for one chunking strategy."""

    strategy_name: str = Field(min_length=1)
    top_chunks: list[RankedChunk]


class QueryRankingComparison(BaseModel):
    """Top-k query ranking across chunking strategies."""

    query: str = Field(min_length=1)
    top_k: int = Field(ge=1)
    strategies: list[QueryStrategyRanking] = Field(min_length=1)


class ChunkingComparisonService:
    """Run chunking strategies over the same budget corpus and summarize them."""

    def __init__(self, strategies: Mapping[str, BudgetChunker] | None = None) -> None:
        self._strategies = dict(strategies) if strategies is not None else {
            "structural_component": JSONStructuralChunker(),
            "whole_budget": WholeBudgetChunker(),
        }

    def compare(self, budgets: list[Budget]) -> ChunkingComparison:
        """Compare all configured strategies on the same budgets."""
        return ChunkingComparison(
            strategies=[
                self._summarize(strategy_name=strategy_name, chunks=chunker.chunk(budgets))
                for strategy_name, chunker in self._strategies.items()
            ]
        )

    def _summarize(
        self,
        strategy_name: str,
        chunks: list[Chunk],
    ) -> ChunkingStrategySummary:
        token_counts = [chunk.token_count for chunk in chunks]
        total_tokens = sum(token_counts)

        return ChunkingStrategySummary(
            strategy_name=strategy_name,
            total_chunks=len(chunks),
            total_tokens=total_tokens,
            min_tokens=min(token_counts, default=0),
            max_tokens=max(token_counts, default=0),
            average_tokens=total_tokens / len(chunks) if chunks else 0,
            chunk_ids=[chunk.chunk_id for chunk in chunks],
        )


class ChunkingQueryComparisonService:
    """Rank chunks for a query across multiple chunking strategies."""

    def __init__(
        self,
        text_embedder: TextEmbedder,
        strategies: Mapping[str, BudgetChunker] | None = None,
    ) -> None:
        self._text_embedder = text_embedder
        self._strategies = dict(strategies) if strategies is not None else {
            "structural_component": JSONStructuralChunker(),
            "whole_budget": WholeBudgetChunker(),
        }

    def compare_query(
        self,
        budgets: list[Budget],
        query: str,
        top_k: int = 3,
    ) -> QueryRankingComparison:
        """Embed a query and rank each strategy's chunks by cosine similarity."""
        if top_k < 1:
            raise ValueError("top_k must be greater than or equal to 1")

        return QueryRankingComparison(
            query=query,
            top_k=top_k,
            strategies=[
                self._rank_strategy(
                    strategy_name=strategy_name,
                    chunks=chunker.chunk(budgets),
                    query=query,
                    top_k=top_k,
                )
                for strategy_name, chunker in self._strategies.items()
            ],
        )

    def _rank_strategy(
        self,
        strategy_name: str,
        chunks: list[Chunk],
        query: str,
        top_k: int,
    ) -> QueryStrategyRanking:
        texts = [query, *[chunk.text for chunk in chunks]]
        vectors = self._text_embedder.embed_texts(texts)

        if len(vectors) != len(texts):
            raise ValueError("text_embedder must return one vector per text")

        query_embedding = vectors[0]
        chunk_embeddings = vectors[1:]

        scored_chunks = sorted(
            (
                (chunk, cosine_similarity(query_embedding, chunk_embedding))
                for chunk, chunk_embedding in zip(chunks, chunk_embeddings, strict=True)
            ),
            key=lambda item: item[1],
            reverse=True,
        )

        return QueryStrategyRanking(
            strategy_name=strategy_name,
            top_chunks=[
                RankedChunk(
                    rank=rank,
                    chunk_id=chunk.chunk_id,
                    score=score,
                    text_preview=_preview_text(chunk.text),
                    metadata=chunk.metadata,
                )
                for rank, (chunk, score) in enumerate(scored_chunks[:top_k], start=1)
            ],
        )


def cosine_similarity(first: list[float], second: list[float]) -> float:
    """Return cosine similarity for two equal-length vectors."""
    if len(first) != len(second):
        raise ValueError("Vectors must have the same length")

    dot_product = sum(a * b for a, b in zip(first, second, strict=True))
    first_norm = math.sqrt(sum(value * value for value in first))
    second_norm = math.sqrt(sum(value * value for value in second))

    if first_norm == 0 or second_norm == 0:
        return 0.0

    return dot_product / (first_norm * second_norm)


def _preview_text(text: str, limit: int = 240) -> str:
    """Collapse whitespace and return a short preview for reports."""
    collapsed = " ".join(text.split())
    return collapsed[:limit]
