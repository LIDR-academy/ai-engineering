import asyncio

from sqlalchemy.dialects import postgresql

from app.persistence.repository import ChunkLexicalSearchResult, DocumentRepository


class FakeRow:
    def __init__(self, **mapping):
        self._mapping = mapping


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class CapturingSession:
    def __init__(self, rows=()):
        self.rows = rows
        self.statement = None

    async def execute(self, statement):
        self.statement = statement
        return FakeResult(self.rows)


def test_lexical_search_builds_postgres_full_text_statement():
    session = CapturingSession()
    repository = DocumentRepository(session)

    asyncio.run(repository.search_chunks_by_text(query_text="OAuth banking", k=7))

    compiled = str(
        session.statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "plainto_tsquery('english', 'OAuth banking')" in compiled
    assert "content_tsv @@ plainto_tsquery" in compiled
    assert "ts_rank_cd" in compiled
    assert "ORDER BY" in compiled
    assert "DESC" in compiled
    assert "LIMIT 7" in compiled


def test_lexical_search_reuses_metadata_filters():
    session = CapturingSession()
    repository = DocumentRepository(session)

    asyncio.run(
        repository.search_chunks_by_text(
            query_text="audit logging",
            k=5,
            metadata_filters={"budget_id": "BUD-2024-014"},
        )
    )

    compiled = str(session.statement.compile(dialect=postgresql.dialect()))

    assert "metadata" in compiled
    assert "@>" in compiled


def test_lexical_search_maps_rows_to_lexical_results():
    session = CapturingSession(
        rows=[
            FakeRow(
                chunk_id=11,
                document_id=22,
                chunk_type="budget_component",
                content="OAuth banking authentication backend",
                rank=0.42,
                metadata={"budget_id": "BUD-2024-014", "component_id": "AUTH-001"},
            )
        ]
    )
    repository = DocumentRepository(session)

    results = asyncio.run(
        repository.search_chunks_by_text(query_text="OAuth banking", k=5)
    )

    assert results == [
        ChunkLexicalSearchResult(
            chunk_id=11,
            document_id=22,
            chunk_type="budget_component",
            content="OAuth banking authentication backend",
            rank=0.42,
            metadata={"budget_id": "BUD-2024-014", "component_id": "AUTH-001"},
        )
    ]
