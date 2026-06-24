import asyncio

from app.embedding_pipeline.search_service import (
    SearchQueryCommand,
    SemanticSearchService,
)
from app.persistence.repository import EMBEDDING_DIMENSION, ChunkSearchResult


class FakeEmbedder:
    def embed_texts(self, texts):
        return [[0.25] * EMBEDDING_DIMENSION]


class VectorRepository:
    async def search_chunks_by_embedding(self, *, query_embedding, k, metadata_filters=None):
        return [
            ChunkSearchResult(
                chunk_id=1,
                document_id=101,
                chunk_type="budget_component",
                content="Generic backend implementation",
                distance=0.10,
                metadata={"budget_id": "BUD-GENERIC"},
            ),
            ChunkSearchResult(
                chunk_id=2,
                document_id=102,
                chunk_type="budget_component",
                content="OAuth banking authentication and audit logging",
                distance=0.20,
                metadata={"budget_id": "BUD-AUTH"},
            ),
            ChunkSearchResult(
                chunk_id=3,
                document_id=103,
                chunk_type="budget_component",
                content="Frontend dashboard polish",
                distance=0.30,
                metadata={"budget_id": "BUD-FRONTEND"},
            ),
        ]


class FakeReranker:
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
        return sorted(
            items,
            key=lambda item: "OAuth banking" not in item.content,
        )[:top_n]


def test_vector_search_can_rerank_candidate_results():
    reranker = FakeReranker()
    service = SemanticSearchService(
        embedder=FakeEmbedder(),
        repository=VectorRepository(),
        reranker=reranker,
    )

    result = asyncio.run(
        service.search(
            SearchQueryCommand(
                query="OAuth banking authentication",
                k=2,
                use_reranker=True,
                rerank_top_n=2,
            )
        )
    )

    assert [item.chunk_id for item in result.results] == [2, 1]
    assert reranker.calls == [
        {
            "query": "OAuth banking authentication",
            "chunk_ids": [1, 2, 3],
            "top_n": 2,
        }
    ]


def test_reranker_is_not_called_when_disabled():
    reranker = FakeReranker()
    service = SemanticSearchService(
        embedder=FakeEmbedder(),
        repository=VectorRepository(),
        reranker=reranker,
    )

    result = asyncio.run(
        service.search(
            SearchQueryCommand(
                query="OAuth banking authentication",
                k=2,
                use_reranker=False,
            )
        )
    )

    assert [item.chunk_id for item in result.results] == [1, 2]
    assert reranker.calls == []


def test_reranker_requires_reranker_when_enabled():
    service = SemanticSearchService(
        embedder=FakeEmbedder(),
        repository=VectorRepository(),
    )

    try:
        asyncio.run(
            service.search(
                SearchQueryCommand(
                    query="OAuth banking authentication",
                    use_reranker=True,
                )
            )
        )
    except ValueError as exc:
        assert "reranker" in str(exc)
    else:
        raise AssertionError("Expected ValueError when reranker is enabled but missing")


class CapturingVectorRepository(VectorRepository):
    def __init__(self):
        self.calls = []

    async def search_chunks_by_embedding(self, *, query_embedding, k, metadata_filters=None):
        self.calls.append(
            {
                "k": k,
                "metadata_filters": metadata_filters,
            }
        )
        return await super().search_chunks_by_embedding(
            query_embedding=query_embedding,
            k=k,
            metadata_filters=metadata_filters,
        )


def test_vector_reranker_uses_recall_width_before_top_k():
    repository = CapturingVectorRepository()
    reranker = FakeReranker()
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
                recall_k=7,
                use_reranker=True,
                rerank_top_n=2,
            )
        )
    )

    assert repository.calls == [
        {
            "k": 7,
            "metadata_filters": {},
        }
    ]
    assert [item.chunk_id for item in result.results] == [2, 1]
