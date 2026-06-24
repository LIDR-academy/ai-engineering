import asyncio

from fastapi.testclient import TestClient

from app.main import app
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


def test_repository_accepts_exact_metadata_filters() -> None:
    from app.persistence.repository import DocumentRepository

    session = FakeAsyncSession(
        rows=[
            FakeRow(
                chunk_id=20,
                document_id=5,
                chunk_type="budget_component",
                content="JWT authentication API for finance",
                distance=0.25,
                metadata={
                    "client_sector": "finance",
                    "year": 2024,
                    "tech_stack": ["python", "fastapi"],
                    "scope": "backend",
                },
            )
        ]
    )
    repository = DocumentRepository(session)

    results = asyncio.run(
        repository.search_chunks_by_embedding(
            query_embedding=[0.1] * EMBEDDING_DIMENSION,
            k=3,
            metadata_filters={
                "client_sector": "finance",
                "year": 2024,
                "tech_stack": ["python"],
                "scope": "backend",
            },
        )
    )

    assert len(results) == 1
    assert results[0].chunk_id == 20
    assert len(session.executed_statements) == 1


def test_search_service_forwards_metadata_filters_to_repository() -> None:
    from app.embedding_pipeline.search_service import (
        SearchMetadataFilters,
        SearchQueryCommand,
        SemanticSearchService,
    )
    from app.persistence.repository import ChunkSearchResult

    class FakeEmbedder:
        def embed_texts(self, texts):
            return [[0.5] * EMBEDDING_DIMENSION]

    class FakeRepository:
        def __init__(self) -> None:
            self.calls = []

        async def search_chunks_by_embedding(self, *, query_embedding, k, metadata_filters=None):
            self.calls.append(
                {
                    "query_embedding": query_embedding,
                    "k": k,
                    "metadata_filters": metadata_filters,
                }
            )
            return [
                ChunkSearchResult(
                    chunk_id=20,
                    document_id=5,
                    chunk_type="budget_component",
                    content="JWT authentication API for finance",
                    distance=0.25,
                    metadata={"client_sector": "finance"},
                )
            ]

    repository = FakeRepository()
    service = SemanticSearchService(embedder=FakeEmbedder(), repository=repository)

    result = asyncio.run(
        service.search(
            SearchQueryCommand(
                query="OAuth backend",
                k=3,
                metadata_filters=SearchMetadataFilters(
                    client_sector="finance",
                    year=2024,
                    tech_stack="python",
                    scope="backend",
                ),
            )
        )
    )

    assert repository.calls == [
        {
            "query_embedding": [0.5] * EMBEDDING_DIMENSION,
            "k": 3,
            "metadata_filters": {
                "client_sector": "finance",
                "year": 2024,
                "tech_stack": ["python"],
                "scope": "backend",
            },
        }
    ]
    assert result.filters_applied == {
        "client_sector": "finance",
        "year": 2024,
        "tech_stack": "python",
        "scope": "backend",
    }


def test_search_endpoint_accepts_metadata_filters(monkeypatch) -> None:
    from app.embedding_pipeline.search_service import SearchQueryResult, SearchResultItem
    from app.routers import search as search_router_module

    class FakeSearchService:
        def __init__(self) -> None:
            self.commands = []

        async def search(self, command):
            self.commands.append(command)
            return SearchQueryResult(
                query=command.query,
                k=command.k,
                filters_applied=command.metadata_filters.as_response_dict(),
                results=[
                    SearchResultItem(
                        chunk_id=20,
                        document_id=5,
                        chunk_type="budget_component",
                        content="JWT authentication API for finance",
                        distance=0.25,
                        metadata={"client_sector": "finance"},
                    )
                ],
            )

    fake_service = FakeSearchService()

    monkeypatch.setattr(
        search_router_module,
        "get_search_service",
        lambda session: fake_service,
    )

    client = TestClient(app)
    response = client.post(
        "/search",
        json={
            "query": "OAuth backend",
            "k": 3,
            "client_sector": "finance",
            "year": 2024,
            "tech_stack": "python",
            "scope": "backend",
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert body["filters_applied"] == {
        "client_sector": "finance",
        "year": 2024,
        "tech_stack": "python",
        "scope": "backend",
    }
    assert fake_service.commands[0].metadata_filters.as_repository_filter() == {
        "client_sector": "finance",
        "year": 2024,
        "tech_stack": ["python"],
        "scope": "backend",
    }
