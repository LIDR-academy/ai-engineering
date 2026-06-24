import asyncio
import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.embedding_pipeline.search_service import SemanticSearchService
from app.main import app
from app.persistence.models import Chunk, Document
from app.persistence.repository import EMBEDDING_DIMENSION, DocumentRepository
from app.routers import search as search_router_module

pytestmark = pytest.mark.skipif(
    os.environ.get("SESSION08_DB_INTEGRATION") != "1",
    reason="Session 08 DB search integration tests require local Postgres and explicit opt-in.",
)


class FakeQueryEmbedder:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        vector = [0.0] * EMBEDDING_DIMENSION
        vector[0] = 1.0
        return [vector]


@pytest.fixture
def db_session_factory() -> Iterator[async_sessionmaker[AsyncSession]]:
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

    async def reset_db() -> None:
        async with factory.begin() as session:
            await session.execute(delete(Chunk))
            await session.execute(delete(Document))

    asyncio.run(reset_db())

    try:
        yield factory
    finally:
        asyncio.run(reset_db())
        asyncio.run(engine.dispose())


def _unit_vector(index: int) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSION
    vector[index] = 1.0
    return vector


async def _seed_search_corpus(factory: async_sessionmaker[AsyncSession]) -> None:
    async with factory.begin() as session:
        document = Document(
            source_path="integration/search-corpus.json",
            document_type="historical_budget",
            document_metadata={"origin": "search-integration"},
        )
        session.add(document)
        await session.flush()

        session.add_all(
            [
                Chunk(
                    document_id=document.id,
                    chunk_type="budget_component",
                    content="OAuth backend API implementation for fintech authentication.",
                    embedding=_unit_vector(0),
                    chunk_metadata={"scope": "backend", "client_sector": "finance"},
                ),
                Chunk(
                    document_id=document.id,
                    chunk_type="budget_component",
                    content="Operations dashboard for admin reporting.",
                    embedding=_unit_vector(1),
                    chunk_metadata={"scope": "frontend", "client_sector": "finance"},
                ),
            ]
        )


def test_session08_search_endpoint_reads_real_pgvector_chunks(
    monkeypatch,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    asyncio.run(_seed_search_corpus(db_session_factory))
    fake_embedder = FakeQueryEmbedder()

    monkeypatch.setattr(search_router_module, "AsyncSessionLocal", db_session_factory)
    monkeypatch.setattr(
        search_router_module,
        "get_search_service",
        lambda session: SemanticSearchService(
            embedder=fake_embedder,
            repository=DocumentRepository(session),
        ),
    )

    client = TestClient(app)
    response = client.post(
        "/search",
        json={
            "query": "OAuth authentication backend",
            "k": 2,
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["query"] == "OAuth authentication backend"
    assert payload["k"] == 2
    assert len(payload["results"]) == 2
    assert fake_embedder.calls == [["OAuth authentication backend"]]

    first, second = payload["results"]
    assert first["content"].startswith("OAuth backend API")
    assert first["distance"] < second["distance"]
    assert first["metadata"]["scope"] == "backend"
    assert second["metadata"]["scope"] == "frontend"


def test_session08_search_endpoint_returns_empty_results_for_empty_corpus(
    monkeypatch,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    monkeypatch.setattr(search_router_module, "AsyncSessionLocal", db_session_factory)
    monkeypatch.setattr(
        search_router_module,
        "get_search_service",
        lambda session: SemanticSearchService(
            embedder=FakeQueryEmbedder(),
            repository=DocumentRepository(session),
        ),
    )

    client = TestClient(app)
    response = client.post(
        "/search",
        json={
            "query": "anything",
            "k": 5,
        },
    )

    assert response.status_code == 200
    assert response.json()["results"] == []


def test_session08_search_endpoint_filters_real_pgvector_chunks_by_metadata(
    monkeypatch,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    asyncio.run(_seed_search_corpus(db_session_factory))
    fake_embedder = FakeQueryEmbedder()

    monkeypatch.setattr(search_router_module, "AsyncSessionLocal", db_session_factory)
    monkeypatch.setattr(
        search_router_module,
        "get_search_service",
        lambda session: SemanticSearchService(
            embedder=fake_embedder,
            repository=DocumentRepository(session),
        ),
    )

    client = TestClient(app)
    response = client.post(
        "/search",
        json={
            "query": "OAuth authentication backend",
            "k": 5,
            "scope": "backend",
            "client_sector": "finance",
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["filters_applied"] == {
        "client_sector": "finance",
        "scope": "backend",
    }
    assert len(payload["results"]) == 1
    assert payload["results"][0]["content"].startswith("OAuth backend API")
    assert payload["results"][0]["metadata"]["scope"] == "backend"
