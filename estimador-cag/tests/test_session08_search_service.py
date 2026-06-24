import asyncio

import pytest

from app.persistence.repository import EMBEDDING_DIMENSION, ChunkSearchResult


class FakeEmbedder:
    def __init__(self) -> None:
        self.calls = []

    def embed_texts(self, texts):
        self.calls.append(texts)
        return [[0.5] * EMBEDDING_DIMENSION]


class MismatchedEmbedder:
    def embed_texts(self, texts):
        return []


class FailingEmbedder:
    def embed_texts(self, texts):
        raise RuntimeError("query provider failed")


class FakeRepository:
    def __init__(self) -> None:
        self.calls = []

    async def search_chunks_by_embedding(self, *, query_embedding, k, metadata_filters=None):
        self.calls.append({"query_embedding": query_embedding, "k": k, "metadata_filters": metadata_filters})
        return [
            ChunkSearchResult(
                chunk_id=10,
                document_id=1,
                chunk_type="budget_component",
                content="Backend API with JWT authentication",
                distance=0.1234,
                metadata={"scope": "backend"},
            )
        ]


def test_semantic_search_service_embeds_query_once_and_returns_results() -> None:
    from app.embedding_pipeline.search_service import (
        SearchQueryCommand,
        SemanticSearchService,
    )

    embedder = FakeEmbedder()
    repository = FakeRepository()
    service = SemanticSearchService(embedder=embedder, repository=repository)

    result = asyncio.run(
        service.search(
            SearchQueryCommand(
                query=" REST API with OAuth authentication ",
                k=5,
            )
        )
    )

    assert result.query == "REST API with OAuth authentication"
    assert result.k == 5
    assert len(result.results) == 1
    assert embedder.calls == [["REST API with OAuth authentication"]]
    assert repository.calls == [
        {
            "query_embedding": [0.5] * EMBEDDING_DIMENSION,
            "k": 5,
            "metadata_filters": {},
        }
    ]

    item = result.results[0]
    assert item.chunk_id == 10
    assert item.document_id == 1
    assert item.chunk_type == "budget_component"
    assert item.content == "Backend API with JWT authentication"
    assert item.distance == 0.1234
    assert item.metadata == {"scope": "backend"}


def test_semantic_search_service_defaults_k_to_5() -> None:
    from app.embedding_pipeline.search_service import (
        SearchQueryCommand,
        SemanticSearchService,
    )

    repository = FakeRepository()
    service = SemanticSearchService(embedder=FakeEmbedder(), repository=repository)

    result = asyncio.run(service.search(SearchQueryCommand(query="OAuth")))

    assert result.k == 5
    assert repository.calls[0]["k"] == 5


def test_semantic_search_service_rejects_blank_query() -> None:
    from app.embedding_pipeline.search_service import (
        SearchQueryCommand,
        SemanticSearchService,
    )

    service = SemanticSearchService(embedder=FakeEmbedder(), repository=FakeRepository())

    with pytest.raises(ValueError, match="query must not be empty"):
        asyncio.run(service.search(SearchQueryCommand(query="   ")))


def test_semantic_search_service_rejects_invalid_k() -> None:
    from app.embedding_pipeline.search_service import (
        SearchQueryCommand,
        SemanticSearchService,
    )

    service = SemanticSearchService(embedder=FakeEmbedder(), repository=FakeRepository())

    with pytest.raises(ValueError, match="k must be positive"):
        asyncio.run(service.search(SearchQueryCommand(query="OAuth", k=0)))


def test_semantic_search_service_rejects_embedding_count_mismatch() -> None:
    from app.embedding_pipeline.search_service import (
        SearchQueryCommand,
        SemanticSearchService,
    )

    repository = FakeRepository()
    service = SemanticSearchService(embedder=MismatchedEmbedder(), repository=repository)

    with pytest.raises(ValueError, match="Query embedding count mismatch"):
        asyncio.run(service.search(SearchQueryCommand(query="OAuth")))

    assert repository.calls == []


def test_semantic_search_service_does_not_query_repository_when_embedder_fails() -> None:
    from app.embedding_pipeline.search_service import (
        SearchQueryCommand,
        SemanticSearchService,
    )

    repository = FakeRepository()
    service = SemanticSearchService(embedder=FailingEmbedder(), repository=repository)

    with pytest.raises(RuntimeError, match="query provider failed"):
        asyncio.run(service.search(SearchQueryCommand(query="OAuth")))

    assert repository.calls == []
