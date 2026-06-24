import asyncio

import pytest

from app.embedding_pipeline.schemas import Chunk
from app.persistence.repository import EMBEDDING_DIMENSION


class FakeChunker:
    def __init__(self) -> None:
        self.calls = []

    def chunk(self, budgets):
        self.calls.append(budgets)
        return [
            Chunk(
                chunk_id="budget-1::api",
                text="Backend API with JWT authentication",
                metadata={"component_id": "api", "scope": "backend"},
                token_count=11,
            ),
            Chunk(
                chunk_id="budget-1::ui",
                text="Admin dashboard for operations",
                metadata={"component_id": "ui", "scope": "frontend"},
                token_count=7,
            ),
        ]


class FakeEmbedder:
    def __init__(self) -> None:
        self.calls = []

    def embed_texts(self, texts):
        self.calls.append(texts)
        return [
            [0.1] * EMBEDDING_DIMENSION,
            [0.2] * EMBEDDING_DIMENSION,
        ]


class FailingEmbedder:
    def embed_texts(self, texts):
        raise RuntimeError("provider failed")


class MismatchedEmbedder:
    def embed_texts(self, texts):
        return [[0.1] * EMBEDDING_DIMENSION]


class FakeRepository:
    def __init__(self, existing_document_id=None) -> None:
        self.existing_document_id = existing_document_id
        self.find_calls = []
        self.add_calls = []

    async def find_document_id_by_source_path(self, source_path):
        self.find_calls.append(source_path)
        return self.existing_document_id

    async def add_document_with_chunks(self, *, source_path, document_type, chunks, metadata=None):
        self.add_calls.append(
            {
                "source_path": source_path,
                "document_type": document_type,
                "chunks": chunks,
                "metadata": metadata,
            }
        )
        return 42


def test_ingestion_service_persists_chunked_budget_with_batch_embeddings() -> None:
    from app.embedding_pipeline.ingestion_service import (
        IngestDocumentCommand,
        PersistentEmbeddingIngestionService,
    )

    chunker = FakeChunker()
    embedder = FakeEmbedder()
    repository = FakeRepository()
    service = PersistentEmbeddingIngestionService(
        chunker=chunker,
        embedder=embedder,
        repository=repository,
    )

    result = asyncio.run(
        service.ingest_document(
            IngestDocumentCommand(
                source_path="data/budgets/budget-1.json",
                document_type="historical_budget",
                budgets=[{"budget_id": "budget-1"}],
                metadata={"origin": "test"},
            )
        )
    )

    assert result.document_id == 42
    assert result.chunks_created == 2
    assert result.embedding_dimension == EMBEDDING_DIMENSION

    assert repository.find_calls == ["data/budgets/budget-1.json"]
    assert chunker.calls == [[{"budget_id": "budget-1"}]]
    assert embedder.calls == [
        [
            "Backend API with JWT authentication",
            "Admin dashboard for operations",
        ]
    ]

    add_call = repository.add_calls[0]
    assert add_call["source_path"] == "data/budgets/budget-1.json"
    assert add_call["document_type"] == "historical_budget"
    assert add_call["metadata"] == {"origin": "test"}

    persisted_chunks = add_call["chunks"]
    assert len(persisted_chunks) == 2
    assert persisted_chunks[0].chunk_type == "budget_component"
    assert persisted_chunks[0].content == "Backend API with JWT authentication"
    assert persisted_chunks[0].embedding == [0.1] * EMBEDDING_DIMENSION
    assert persisted_chunks[0].metadata["chunk_id"] == "budget-1::api"
    assert persisted_chunks[0].metadata["token_count"] == 11
    assert persisted_chunks[0].metadata["component_id"] == "api"


def test_ingestion_service_raises_duplicate_before_chunking_or_embedding() -> None:
    from app.embedding_pipeline.ingestion_service import (
        DocumentAlreadyIngestedError,
        IngestDocumentCommand,
        PersistentEmbeddingIngestionService,
    )

    chunker = FakeChunker()
    embedder = FakeEmbedder()
    repository = FakeRepository(existing_document_id=99)
    service = PersistentEmbeddingIngestionService(
        chunker=chunker,
        embedder=embedder,
        repository=repository,
    )

    with pytest.raises(DocumentAlreadyIngestedError) as exc_info:
        asyncio.run(
            service.ingest_document(
                IngestDocumentCommand(
                    source_path="data/budgets/duplicate.json",
                    document_type="historical_budget",
                    budgets=[{"budget_id": "duplicate"}],
                )
            )
        )

    assert exc_info.value.document_id == 99
    assert chunker.calls == []
    assert embedder.calls == []
    assert repository.add_calls == []


def test_ingestion_service_does_not_persist_when_embedder_fails() -> None:
    from app.embedding_pipeline.ingestion_service import (
        IngestDocumentCommand,
        PersistentEmbeddingIngestionService,
    )

    repository = FakeRepository()
    service = PersistentEmbeddingIngestionService(
        chunker=FakeChunker(),
        embedder=FailingEmbedder(),
        repository=repository,
    )

    with pytest.raises(RuntimeError, match="provider failed"):
        asyncio.run(
            service.ingest_document(
                IngestDocumentCommand(
                    source_path="data/budgets/failure.json",
                    document_type="historical_budget",
                    budgets=[{"budget_id": "failure"}],
                )
            )
        )

    assert repository.add_calls == []


def test_ingestion_service_rejects_embedding_count_mismatch() -> None:
    from app.embedding_pipeline.ingestion_service import (
        IngestDocumentCommand,
        PersistentEmbeddingIngestionService,
    )

    repository = FakeRepository()
    service = PersistentEmbeddingIngestionService(
        chunker=FakeChunker(),
        embedder=MismatchedEmbedder(),
        repository=repository,
    )

    with pytest.raises(ValueError, match="Embedding count mismatch"):
        asyncio.run(
            service.ingest_document(
                IngestDocumentCommand(
                    source_path="data/budgets/mismatch.json",
                    document_type="historical_budget",
                    budgets=[{"budget_id": "mismatch"}],
                )
            )
        )

    assert repository.add_calls == []
