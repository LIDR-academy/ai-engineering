import os
from collections.abc import AsyncIterator

import pytest
import sqlalchemy as sa
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.embedding_pipeline.chunker import JSONStructuralChunker
from app.embedding_pipeline.ingestion_service import (
    DocumentAlreadyIngestedError,
    IngestDocumentCommand,
    PersistentEmbeddingIngestionService,
)
from app.embedding_pipeline.schemas import Budget
from app.persistence.models import Chunk, Document
from app.persistence.repository import EMBEDDING_DIMENSION, DocumentRepository

pytestmark = pytest.mark.skipif(
    os.environ.get("SESSION08_DB_INTEGRATION") != "1",
    reason="Session 08 DB integration tests require local Postgres and explicit opt-in.",
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    database_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://estimator:estimator@localhost:5432/estimator",
    )
    engine = create_async_engine(database_url, poolclass=NullPool)
    factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    try:
        async with factory.begin() as session:
            await session.execute(delete(Chunk))
            await session.execute(delete(Document))

        yield factory

        async with factory.begin() as session:
            await session.execute(delete(Chunk))
            await session.execute(delete(Document))
    finally:
        await engine.dispose()


class FakeEmbedder:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [[float(index)] * EMBEDDING_DIMENSION for index, _ in enumerate(texts, start=1)]


class FailingEmbedder:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("fake provider failed")


def sample_budget() -> Budget:
    return Budget.model_validate(
        {
            "budget_id": "BUD-DB-001",
            "client_metadata": {
                "name": "FintechCorp",
                "sector": "finance",
                "country": "ES",
            },
            "project_summary": "Mobile banking API with OAuth authentication",
            "main_technology": "python",
            "year": 2024,
            "total_estimated_hours": 200,
            "components": [
                {
                    "component_id": "AUTH-001",
                    "name": "JWT authentication backend",
                    "description": "Token-based access control for banking APIs.",
                    "tech_stack": ["python", "fastapi", "postgresql"],
                    "estimated_hours": 120,
                    "complexity": "high",
                    "dependencies": [],
                },
                {
                    "component_id": "AUDIT-001",
                    "name": "Audit trail",
                    "description": "Immutable log of regulated account operations.",
                    "tech_stack": ["python", "postgresql"],
                    "estimated_hours": 80,
                    "complexity": "medium",
                    "dependencies": ["AUTH-001"],
                },
            ],
        }
    )


@pytest.mark.anyio
async def test_session08_db_ingest_persists_document_and_chunks(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    embedder = FakeEmbedder()

    async with session_factory.begin() as session:
        service = PersistentEmbeddingIngestionService(
            chunker=JSONStructuralChunker(),
            embedder=embedder,
            repository=DocumentRepository(session),
        )

        result = await service.ingest_document(
            IngestDocumentCommand(
                source_path="integration/budget-db-001.json",
                document_type="historical_budget",
                budgets=[sample_budget()],
                metadata={"origin": "integration-test"},
            )
        )

    async with session_factory() as session:
        documents = (
            await session.execute(
                select(Document).where(Document.source_path == "integration/budget-db-001.json")
            )
        ).scalars().all()
        chunks = (
            await session.execute(
                select(Chunk).where(Chunk.document_id == result.document_id).order_by(Chunk.id)
            )
        ).scalars().all()

    assert result.document_id > 0
    assert result.chunks_created == 2
    assert result.embedding_dimension == EMBEDDING_DIMENSION
    assert len(embedder.calls) == 1
    assert len(embedder.calls[0]) == 2

    assert len(documents) == 1
    assert documents[0].document_metadata == {"origin": "integration-test"}

    assert len(chunks) == 2
    assert chunks[0].content.startswith("[Project: Mobile banking API")
    assert list(chunks[0].embedding) == [1.0] * EMBEDDING_DIMENSION
    assert chunks[0].chunk_metadata["budget_id"] == "BUD-DB-001"
    assert chunks[0].chunk_metadata["chunk_id"] == "BUD-DB-001::AUTH-001"


@pytest.mark.anyio
async def test_session08_db_ingest_detects_duplicate_source_path(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory.begin() as session:
        service = PersistentEmbeddingIngestionService(
            chunker=JSONStructuralChunker(),
            embedder=FakeEmbedder(),
            repository=DocumentRepository(session),
        )

        command = IngestDocumentCommand(
            source_path="integration/duplicate.json",
            document_type="historical_budget",
            budgets=[sample_budget()],
        )

        first_result = await service.ingest_document(command)

        with pytest.raises(DocumentAlreadyIngestedError) as exc_info:
            await service.ingest_document(command)

    assert exc_info.value.document_id == first_result.document_id


@pytest.mark.anyio
async def test_session08_db_ingest_failure_leaves_no_orphan_document(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory.begin() as session:
        service = PersistentEmbeddingIngestionService(
            chunker=JSONStructuralChunker(),
            embedder=FailingEmbedder(),
            repository=DocumentRepository(session),
        )

        with pytest.raises(RuntimeError, match="fake provider failed"):
            await service.ingest_document(
                IngestDocumentCommand(
                    source_path="integration/failure.json",
                    document_type="historical_budget",
                    budgets=[sample_budget()],
                )
            )

    async with session_factory() as session:
        document_id = await DocumentRepository(session).find_document_id_by_source_path(
            "integration/failure.json"
        )

    assert document_id is None


@pytest.mark.anyio
async def test_session08_db_schema_has_expected_hnsw_cosine_vector_index(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        result = await session.execute(
            sa.text(
                """
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename = 'chunks'
                  AND indexname = 'ix_chunks_embedding_hnsw_cosine'
                """
            )
        )

    rows = result.mappings().all()

    assert len(rows) == 1
    indexdef = rows[0]["indexdef"].lower()
    assert "using hnsw" in indexdef
    assert "vector_cosine_ops" in indexdef
    assert "embedding is not null" in indexdef
