from __future__ import annotations

from fastapi.testclient import TestClient

import app.embedding_pipeline.router as embedding_router_module
from app.embedding_pipeline.comparison import (
    QueryRankingComparison,
    QueryStrategyRanking,
    RankedChunk,
)
from app.embedding_pipeline.ingestion_service import (
    DocumentAlreadyIngestedError,
    IngestDocumentResult,
)
from app.main import app


def sample_budget_payload() -> dict:
    return {
        "budget_id": "BUD-2024-014",
        "client_metadata": {
            "name": "FintechCorp",
            "sector": "finance",
            "country": "ES",
        },
        "project_summary": "Mobile banking API with OAuth 2.0 authentication and PSD2 compliance",
        "main_technology": "ruby_on_rails",
        "year": 2024,
        "total_estimated_hours": 480,
        "components": [
            {
                "component_id": "AUTH-001",
                "name": "OAuth 2.0 authentication backend",
                "description": (
                    "Implementation of OAuth 2.0 flows with JWT-based session management, "
                    "multi-tenant token isolation, and rate limiting per client."
                ),
                "tech_stack": ["ruby_on_rails", "postgresql", "redis"],
                "estimated_hours": 120,
                "complexity": "high",
                "dependencies": [],
            },
            {
                "component_id": "AUDIT-001",
                "name": "Audit logging",
                "description": "Immutable audit trail for regulated account operations.",
                "tech_stack": ["ruby_on_rails", "postgresql"],
                "estimated_hours": 80,
                "complexity": "medium",
                "dependencies": ["AUTH-001"],
            },
        ],
    }


class FakePersistentIngestionService:
    def __init__(self) -> None:
        self.commands = []

    async def ingest_document(self, command):
        self.commands.append(command)
        return IngestDocumentResult(
            document_id=42,
            chunks_created=2,
            embedding_dimension=1536,
        )


class FailingPersistentIngestionService:
    async def ingest_document(self, command):
        raise RuntimeError("provider exploded with internal details")


class DuplicatePersistentIngestionService:
    async def ingest_document(self, command):
        raise DocumentAlreadyIngestedError(document_id=99)


def test_embeddings_ingest_returns_persistent_document_response(monkeypatch) -> None:
    fake_service = FakePersistentIngestionService()

    monkeypatch.setattr(
        embedding_router_module,
        "get_persistent_ingestion_service",
        lambda session: fake_service,
    )

    client = TestClient(app)
    response = client.post(
        "/embeddings/ingest",
        json={
            "source_path": "data/budgets/budget-1.json",
            "document_type": "historical_budget",
            "content": {"budgets": [sample_budget_payload()]},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["document_id"] == 42
    assert payload["chunks_created"] == 2
    assert payload["embedding_dimension"] == 1536
    assert isinstance(payload["ingestion_time_ms"], int)
    assert payload["ingestion_time_ms"] >= 0

    assert len(fake_service.commands) == 1
    command = fake_service.commands[0]
    assert command.source_path == "data/budgets/budget-1.json"
    assert command.document_type == "historical_budget"
    assert [budget.model_dump(mode="json") for budget in command.budgets] == [
        sample_budget_payload()
    ]
    assert command.metadata == {"content_keys": ["budgets"]}


def test_embeddings_ingest_duplicate_returns_409(monkeypatch) -> None:
    monkeypatch.setattr(
        embedding_router_module,
        "get_persistent_ingestion_service",
        lambda session: DuplicatePersistentIngestionService(),
    )

    client = TestClient(app)
    response = client.post(
        "/embeddings/ingest",
        json={
            "source_path": "data/budgets/duplicate.json",
            "document_type": "historical_budget",
            "content": {"budgets": [sample_budget_payload()]},
        },
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Document already ingested",
        "document_id": 99,
    }


def test_embeddings_ingest_uses_pydantic_validation_without_openai_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    client = TestClient(app)
    response = client.post(
        "/embeddings/ingest",
        json={
            "source_path": "",
            "document_type": "historical_budget",
            "content": {"budgets": []},
        },
    )

    assert response.status_code == 422


def test_embeddings_ingest_rejects_missing_content_budgets_without_openai_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    client = TestClient(app)
    response = client.post(
        "/embeddings/ingest",
        json={
            "source_path": "data/budgets/missing.json",
            "document_type": "historical_budget",
            "content": {},
        },
    )

    assert response.status_code == 422


def test_embeddings_ingest_returns_generic_500_for_service_errors(monkeypatch) -> None:
    monkeypatch.setattr(
        embedding_router_module,
        "get_persistent_ingestion_service",
        lambda session: FailingPersistentIngestionService(),
    )

    client = TestClient(app)
    response = client.post(
        "/embeddings/ingest",
        json={
            "source_path": "data/budgets/failure.json",
            "document_type": "historical_budget",
            "content": {"budgets": [sample_budget_payload()]},
        },
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Embedding ingestion failed"}


def test_embeddings_compare_returns_strategy_rankings() -> None:
    client = TestClient(app)

    response = client.post(
        "/embeddings/compare",
        json={
            "budgets": [sample_budget_payload()],
            "query": "OAuth JWT authentication banking authorization",
            "top_k": 1,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["query"] == "OAuth JWT authentication banking authorization"
    assert body["top_k"] == 1

    by_name = {strategy["strategy_name"]: strategy for strategy in body["strategies"]}

    assert set(by_name) == {"structural_component", "whole_budget"}

    structural_top = by_name["structural_component"]["top_chunks"][0]
    whole_budget_top = by_name["whole_budget"]["top_chunks"][0]

    assert structural_top["rank"] == 1
    assert structural_top["chunk_id"] == "BUD-2024-014::AUTH-001"
    assert structural_top["score"] > 0

    assert whole_budget_top["rank"] == 1
    assert whole_budget_top["chunk_id"] == "BUD-2024-014::whole_budget"
    assert whole_budget_top["score"] > 0


def test_embeddings_compare_rejects_invalid_top_k() -> None:
    client = TestClient(app)

    response = client.post(
        "/embeddings/compare",
        json={
            "budgets": [sample_budget_payload()],
            "query": "OAuth",
            "top_k": 0,
        },
    )

    assert response.status_code == 422


def test_embeddings_routes_are_registered_in_openapi() -> None:
    client = TestClient(app)

    schema = client.get("/openapi.json").json()

    assert "/embeddings/ingest" in schema["paths"]
    assert "/embeddings/compare" in schema["paths"]


class FakeQueryComparisonService:
    def compare_query(self, budgets, query: str, top_k: int) -> QueryRankingComparison:
        return QueryRankingComparison(
            query=query,
            top_k=top_k,
            strategies=[
                QueryStrategyRanking(
                    strategy_name="fake_strategy",
                    top_chunks=[
                        RankedChunk(
                            rank=1,
                            chunk_id="fake::chunk",
                            score=0.99,
                            text_preview="fake preview",
                            metadata={"budget_id": "fake-budget"},
                        )
                    ],
                )
            ],
        )


def test_embeddings_compare_can_override_comparison_service_dependency() -> None:
    app.dependency_overrides[
        embedding_router_module.get_query_comparison_service
    ] = lambda: FakeQueryComparisonService()

    try:
        client = TestClient(app)

        response = client.post(
            "/embeddings/compare",
            json={
                "budgets": [sample_budget_payload()],
                "query": "OAuth",
                "top_k": 1,
            },
        )

        assert response.status_code == 200

        body = response.json()
        assert body["strategies"][0]["strategy_name"] == "fake_strategy"
        assert body["strategies"][0]["top_chunks"][0]["chunk_id"] == "fake::chunk"
    finally:
        app.dependency_overrides.clear()
