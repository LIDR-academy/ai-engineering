"""
LAYER: semantic search service
RESPONSIBILITY: Embed a query and retrieve nearest persisted chunks by cosine distance.
WHY IT EXISTS: Session 08 introduces pgvector retrieval before wiring the /search API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.embedding_pipeline.fusion import DEFAULT_RRF_K, reciprocal_rank_fusion
from app.persistence.repository import (
    ChunkLexicalSearchResult,
    ChunkSearchResult,
    DocumentRepository,
)

LEXICAL_ONLY_DISTANCE = 999.0
VALID_SEARCH_MODES = {"vector", "hybrid"}


class SearchReranker(Protocol):
    """Optional second-stage reranker for retrieved search candidates."""

    def rerank(
        self,
        *,
        query: str,
        items: list[SearchResultItem],
        top_n: int,
    ) -> list[SearchResultItem]:
        """Return items reordered by query-specific relevance."""


class QueryEmbedder(Protocol):
    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


@dataclass(frozen=True)
class SearchMetadataFilters:
    """Exact metadata filters accepted by semantic search."""

    client_sector: str | None = None
    client_country: str | None = None
    main_technology: str | None = None
    complexity: str | None = None
    year: int | None = None
    budget_id: str | None = None
    component_id: str | None = None
    tech_stack: str | None = None
    scope: str | None = None

    def as_response_dict(self) -> dict[str, Any]:
        """Return non-empty filter values as the public response representation."""
        filters: dict[str, Any] = {}
        for key in [
            "client_sector",
            "client_country",
            "main_technology",
            "complexity",
            "year",
            "budget_id",
            "component_id",
            "tech_stack",
            "scope",
        ]:
            value = getattr(self, key)
            if value is None:
                continue
            if isinstance(value, str):
                stripped = value.strip()
                if stripped:
                    filters[key] = stripped
                continue
            filters[key] = value
        return filters

    def as_repository_filter(self) -> dict[str, Any]:
        """Return JSONB containment filters for repository search."""
        filters = self.as_response_dict()
        if "tech_stack" in filters:
            filters["tech_stack"] = [filters["tech_stack"]]
        return filters


@dataclass(frozen=True)
class SearchQueryCommand:
    """Input command for semantic or hybrid chunk search."""

    query: str
    k: int = 5
    metadata_filters: SearchMetadataFilters = field(default_factory=SearchMetadataFilters)
    search_mode: str = "vector"
    recall_k: int = 50
    rrf_k: int = DEFAULT_RRF_K
    use_reranker: bool = False
    rerank_top_n: int = 5


@dataclass(frozen=True)
class SearchResultItem:
    """One result returned from semantic search."""

    chunk_id: int
    document_id: int
    chunk_type: str
    content: str
    distance: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SearchQueryResult:
    """Semantic search result envelope."""

    query: str
    k: int
    results: list[SearchResultItem]
    filters_applied: dict[str, Any] = field(default_factory=dict)


class SemanticSearchService:
    """Application service for query embedding plus pgvector retrieval."""

    def __init__(
        self,
        *,
        embedder: QueryEmbedder,
        repository: DocumentRepository,
        reranker: SearchReranker | None = None,
    ) -> None:
        self.embedder = embedder
        self.repository = repository
        self.reranker = reranker

    async def search(self, command: SearchQueryCommand) -> SearchQueryResult:
        """Embed the query once and return persisted chunks.

        ``search_mode="vector"`` preserves the Session 08 baseline.
        ``search_mode="hybrid"`` recalls vector and lexical candidates, then
        fuses both rankings with Reciprocal Rank Fusion.
        """

        query = command.query.strip()
        if not query:
            raise ValueError("query must not be empty")
        if command.k <= 0:
            raise ValueError("k must be positive")
        if command.recall_k <= 0:
            raise ValueError("recall_k must be positive")
        if command.search_mode not in VALID_SEARCH_MODES:
            raise ValueError("search_mode must be 'vector' or 'hybrid'")
        if command.rerank_top_n <= 0:
            raise ValueError("rerank_top_n must be positive")
        if command.use_reranker and self.reranker is None:
            raise ValueError("reranker is required when use_reranker is true")

        embeddings = self.embedder.embed_texts([query])
        if len(embeddings) != 1:
            raise ValueError("Query embedding count mismatch")

        query_embedding = embeddings[0]
        repository_filters = command.metadata_filters.as_repository_filter()

        if command.search_mode == "vector":
            retrieval_k = (
                max(command.k, command.recall_k) if command.use_reranker else command.k
            )
            rows = await self.repository.search_chunks_by_embedding(
                query_embedding=query_embedding,
                k=retrieval_k,
                metadata_filters=repository_filters,
            )
            results = [_to_search_result_item(row) for row in rows]
        else:
            recall_k = max(command.k, command.recall_k)
            vector_rows = await self.repository.search_chunks_by_embedding(
                query_embedding=query_embedding,
                k=recall_k,
                metadata_filters=repository_filters,
            )
            lexical_rows = await self.repository.search_chunks_by_text(
                query_text=query,
                k=recall_k,
                metadata_filters=repository_filters,
            )
            fusion_top_k = recall_k if command.use_reranker else command.k
            results = _to_hybrid_search_result_items(
                vector_rows=vector_rows,
                lexical_rows=lexical_rows,
                top_k=fusion_top_k,
                rrf_k=command.rrf_k,
            )

        if command.use_reranker:
            results = self.reranker.rerank(
                query=query,
                items=results,
                top_n=min(command.rerank_top_n, command.k),
            )

        return SearchQueryResult(
            query=query,
            k=command.k,
            results=results[: command.k],
            filters_applied=command.metadata_filters.as_response_dict(),
        )


def _to_search_result_item(row: ChunkSearchResult) -> SearchResultItem:
    return SearchResultItem(
        chunk_id=row.chunk_id,
        document_id=row.document_id,
        chunk_type=row.chunk_type,
        content=row.content,
        distance=row.distance,
        metadata=row.metadata,
    )


def _to_hybrid_search_result_items(
    *,
    vector_rows: list[ChunkSearchResult],
    lexical_rows: list[ChunkLexicalSearchResult],
    top_k: int,
    rrf_k: int,
) -> list[SearchResultItem]:
    vector_by_chunk_id = {row.chunk_id: row for row in vector_rows}
    lexical_by_chunk_id = {row.chunk_id: row for row in lexical_rows}

    fused = reciprocal_rank_fusion(
        {
            "vector": [row.chunk_id for row in vector_rows],
            "lexical": [row.chunk_id for row in lexical_rows],
        },
        k=rrf_k,
        limit=top_k,
    )

    results: list[SearchResultItem] = []
    for fused_item in fused:
        chunk_id = int(fused_item.document_id)

        if chunk_id in vector_by_chunk_id:
            results.append(_to_search_result_item(vector_by_chunk_id[chunk_id]))
            continue

        lexical_row = lexical_by_chunk_id[chunk_id]
        results.append(
            SearchResultItem(
                chunk_id=lexical_row.chunk_id,
                document_id=lexical_row.document_id,
                chunk_type=lexical_row.chunk_type,
                content=lexical_row.content,
                distance=LEXICAL_ONLY_DISTANCE,
                metadata=lexical_row.metadata,
            )
        )

    return results
