import pytest

from app.persistence.models import Chunk, Document
from app.persistence.repository import (
    EMBEDDING_DIMENSION,
    ChunkInsert,
    DocumentRepository,
)


class FakeScalarResult:
    def __init__(self, value: int | None) -> None:
        self.value = value

    def scalar_one_or_none(self) -> int | None:
        return self.value


class FakeAsyncSession:
    def __init__(self, existing_document_id: int | None = None) -> None:
        self.existing_document_id = existing_document_id
        self.added = []
        self.executed_statements = []
        self.flush_calls = 0
        self.commit_calls = 0

    async def execute(self, statement):
        self.executed_statements.append(statement)
        return FakeScalarResult(self.existing_document_id)

    def add(self, instance) -> None:
        self.added.append(instance)

    async def flush(self) -> None:
        self.flush_calls += 1
        for instance in self.added:
            if isinstance(instance, Document) and instance.id is None:
                instance.id = 42

    async def commit(self) -> None:
        self.commit_calls += 1


@pytest.mark.parametrize(
    "embedding",
    [
        [0.1] * EMBEDDING_DIMENSION,
        None,
    ],
)
def test_chunk_insert_accepts_valid_embedding_dimensions(embedding) -> None:
    chunk = ChunkInsert(
        chunk_type="budget_component",
        content="Backend API with JWT authentication",
        embedding=embedding,
        metadata={"scope": "backend"},
    )

    assert chunk.embedding == embedding


def test_chunk_insert_rejects_wrong_embedding_dimension() -> None:
    with pytest.raises(ValueError, match="Embedding dimension must be 1536"):
        ChunkInsert(
            chunk_type="budget_component",
            content="Bad vector",
            embedding=[0.1, 0.2],
            metadata={},
        )


def test_repository_rejects_empty_chunk_list() -> None:
    import asyncio

    repository = DocumentRepository(FakeAsyncSession())

    with pytest.raises(ValueError, match="At least one chunk is required"):
        asyncio.run(
            repository.add_document_with_chunks(
                source_path="data/budgets/example.json",
                document_type="historical_budget",
                chunks=[],
                metadata={},
            )
        )


async def _find_document_id_by_source_path(existing_document_id: int | None) -> int | None:
    session = FakeAsyncSession(existing_document_id=existing_document_id)
    repository = DocumentRepository(session)

    result = await repository.find_document_id_by_source_path("data/budgets/example.json")

    assert len(session.executed_statements) == 1
    return result


def test_find_document_id_by_source_path_returns_existing_id() -> None:
    import asyncio

    result = asyncio.run(_find_document_id_by_source_path(existing_document_id=123))

    assert result == 123


def test_find_document_id_by_source_path_returns_none_when_missing() -> None:
    import asyncio

    result = asyncio.run(_find_document_id_by_source_path(existing_document_id=None))

    assert result is None


def test_add_document_with_chunks_adds_document_and_chunks_without_commit() -> None:
    import asyncio

    session = FakeAsyncSession()
    repository = DocumentRepository(session)

    document_id = asyncio.run(
        repository.add_document_with_chunks(
            source_path="data/budgets/example.json",
            document_type="historical_budget",
            metadata={"source": "test"},
            chunks=[
                ChunkInsert(
                    chunk_type="budget_component",
                    content="Backend API with JWT authentication",
                    embedding=[0.1] * EMBEDDING_DIMENSION,
                    metadata={"scope": "backend"},
                ),
                ChunkInsert(
                    chunk_type="budget_summary",
                    content="Fintech platform modernization",
                    embedding=[0.2] * EMBEDDING_DIMENSION,
                    metadata={"scope": "summary"},
                ),
            ],
        )
    )

    assert document_id == 42
    assert session.commit_calls == 0
    assert session.flush_calls == 2

    document = session.added[0]
    assert isinstance(document, Document)
    assert document.source_path == "data/budgets/example.json"
    assert document.document_type == "historical_budget"
    assert document.document_metadata == {"source": "test"}

    chunks = session.added[1:]
    assert len(chunks) == 2
    assert all(isinstance(chunk, Chunk) for chunk in chunks)
    assert [chunk.document_id for chunk in chunks] == [42, 42]
    assert [chunk.chunk_type for chunk in chunks] == ["budget_component", "budget_summary"]
    assert chunks[0].embedding == [0.1] * EMBEDDING_DIMENSION
    assert chunks[1].chunk_metadata == {"scope": "summary"}
