import asyncio

import pytest

from app.embedding_pipeline.search_service import (
    LEXICAL_ONLY_DISTANCE,
    SearchMetadataFilters,
    SearchQueryCommand,
    SemanticSearchService,
)
from app.persistence.repository import (
    EMBEDDING_DIMENSION,
    ChunkLexicalSearchResult,
    ChunkSearchResult,
)


class FakeEmbedder:
    def __init__(self) -> None:
        self.calls = []

    def embed_texts(self, texts):
        self.calls.append(texts)
        return [[0.25] * EMBEDDING_DIMENSION]


class HybridRepository:
    def __init__(self) -> None:
        self.vector_calls = []
        self.lexical_calls = []

    async def search_chunks_by_embedding(self, *, query_embedding, k, metadata_filters=None):
        self.vector_calls.append(
            {
                "query_embedding": query_embedding,
                "k": k,
                "metadata_filters": metadata_filters,
            }
        )
        return [
            ChunkSearchResult(
                chunk_id=1,
                document_id=101,
                chunk_type="budget_component",
                content="Vector only API authentication chunk",
                distance=0.10,
                metadata={"budget_id": "BUD-VECTOR"},
            ),
            ChunkSearchResult(
                chunk_id=2,
                document_id=102,
                chunk_type="budget_component",
                content="Shared OAuth banking authentication chunk",
                distance=0.20,
                metadata={"budget_id": "BUD-SHARED"},
            ),
        ]

    async def search_chunks_by_text(self, *, query_text, k, metadata_filters=None):
        self.lexical_calls.append(
            {
                "query_text": query_text,
                "k": k,
                "metadata_filters": metadata_filters,
            }
        )
        return [
            ChunkLexicalSearchResult(
                chunk_id=2,
                document_id=102,
                chunk_type="budget_component",
                content="Shared OAuth banking authentication chunk",
                rank=0.90,
                metadata={"budget_id": "BUD-SHARED"},
            ),
            ChunkLexicalSearchResult(
                chunk_id=3,
                document_id=103,
                chunk_type="budget_component",
                content="Lexical only audit logging chunk",
                rank=0.80,
                metadata={"budget_id": "BUD-LEXICAL"},
            ),
        ]


def test_hybrid_search_fuses_vector_and_lexical_rankings():
    repository = HybridRepository()
    service = SemanticSearchService(embedder=FakeEmbedder(), repository=repository)

    result = asyncio.run(
        service.search(
            SearchQueryCommand(
                query=" OAuth banking authentication ",
                k=3,
                search_mode="hybrid",
                recall_k=3,
            )
        )
    )

    assert result.query == "OAuth banking authentication"
    assert result.k == 3
    assert [item.chunk_id for item in result.results] == [2, 1, 3]
    assert result.results[0].metadata == {"budget_id": "BUD-SHARED"}
    assert result.results[2].distance == LEXICAL_ONLY_DISTANCE

    assert repository.vector_calls == [
        {
            "query_embedding": [0.25] * EMBEDDING_DIMENSION,
            "k": 3,
            "metadata_filters": {},
        }
    ]
    assert repository.lexical_calls == [
        {
            "query_text": "OAuth banking authentication",
            "k": 3,
            "metadata_filters": {},
        }
    ]


def test_hybrid_search_uses_recall_width_and_keeps_top_k():
    repository = HybridRepository()
    service = SemanticSearchService(embedder=FakeEmbedder(), repository=repository)

    result = asyncio.run(
        service.search(
            SearchQueryCommand(
                query="OAuth banking",
                k=2,
                search_mode="hybrid",
                recall_k=5,
                metadata_filters=SearchMetadataFilters(budget_id="BUD-2024-014"),
            )
        )
    )

    assert len(result.results) == 2
    assert repository.vector_calls[0]["k"] == 5
    assert repository.lexical_calls[0]["k"] == 5
    assert repository.vector_calls[0]["metadata_filters"] == {"budget_id": "BUD-2024-014"}
    assert repository.lexical_calls[0]["metadata_filters"] == {"budget_id": "BUD-2024-014"}


def test_hybrid_search_rejects_unknown_search_mode():
    service = SemanticSearchService(embedder=FakeEmbedder(), repository=HybridRepository())

    with pytest.raises(ValueError, match="search_mode"):
        asyncio.run(
            service.search(
                SearchQueryCommand(
                    query="OAuth banking",
                    search_mode="telepathy",
                )
            )
        )


class CapturingReranker:
    def __init__(self):
        self.calls = []

    def rerank(self, *, query, items, top_n):
        self.calls.append(
            {
                "query": query,
                "chunk_ids": [item.chunk_id for item in items],
                "top_n": top_n,
            }
        )
        return items[:top_n]


def test_hybrid_reranker_receives_recall_width_fused_candidates():
    repository = HybridRepository()
    reranker = CapturingReranker()
    service = SemanticSearchService(
        embedder=FakeEmbedder(),
        repository=repository,
        reranker=reranker,
    )

    result = asyncio.run(
        service.search(
            SearchQueryCommand(
                query="OAuth banking authentication",
                k=2,
                search_mode="hybrid",
                recall_k=7,
                use_reranker=True,
                rerank_top_n=2,
            )
        )
    )

    assert repository.vector_calls[0]["k"] == 7
    assert repository.lexical_calls[0]["k"] == 7
    assert reranker.calls == [
        {
            "query": "OAuth banking authentication",
            "chunk_ids": [2, 1, 3],
            "top_n": 2,
        }
    ]
    assert [item.chunk_id for item in result.results] == [2, 1]
