import asyncio

import pytest

from app.persistence.repository import EMBEDDING_DIMENSION


class FakeRow:
    def __init__(self, **values) -> None:
        self._mapping = values


class FakeSearchResult:
    def __init__(self, rows) -> None:
        self.rows = rows

    def all(self):
        return self.rows


class FakeAsyncSession:
    def __init__(self, rows=None) -> None:
        self.rows = rows or []
        self.executed_statements = []

    async def execute(self, statement):
        self.executed_statements.append(statement)
        return FakeSearchResult(self.rows)


def test_search_chunks_by_embedding_maps_rows_to_results() -> None:
    from app.persistence.repository import DocumentRepository

    session = FakeAsyncSession(
        rows=[
            FakeRow(
                chunk_id=10,
                document_id=1,
                chunk_type="budget_component",
                content="Backend API with JWT authentication",
                distance=0.1234,
                metadata={"scope": "backend"},
            ),
            FakeRow(
                chunk_id=11,
                document_id=2,
                chunk_type="budget_component",
                content="Admin dashboard",
                distance=0.4567,
                metadata={"scope": "frontend"},
            ),
        ]
    )
    repository = DocumentRepository(session)

    results = asyncio.run(
        repository.search_chunks_by_embedding(
            query_embedding=[0.1] * EMBEDDING_DIMENSION,
            k=2,
        )
    )

    assert len(session.executed_statements) == 1
    assert [result.chunk_id for result in results] == [10, 11]
    assert [result.document_id for result in results] == [1, 2]
    assert [result.chunk_type for result in results] == [
        "budget_component",
        "budget_component",
    ]
    assert results[0].content == "Backend API with JWT authentication"
    assert results[0].distance == 0.1234
    assert results[0].metadata == {"scope": "backend"}


def test_search_chunks_by_embedding_rejects_invalid_k() -> None:
    from app.persistence.repository import DocumentRepository

    repository = DocumentRepository(FakeAsyncSession())

    with pytest.raises(ValueError, match="k must be positive"):
        asyncio.run(
            repository.search_chunks_by_embedding(
                query_embedding=[0.1] * EMBEDDING_DIMENSION,
                k=0,
            )
        )


def test_search_chunks_by_embedding_rejects_wrong_query_dimension() -> None:
    from app.persistence.repository import DocumentRepository

    repository = DocumentRepository(FakeAsyncSession())

    with pytest.raises(ValueError, match="Embedding dimension must be 1536"):
        asyncio.run(
            repository.search_chunks_by_embedding(
                query_embedding=[0.1, 0.2],
                k=5,
            )
        )
