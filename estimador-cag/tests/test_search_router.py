from fastapi.testclient import TestClient

from app.embedding_pipeline.search_service import SearchQueryResult, SearchResultItem
from app.main import app


class FakeSearchService:
    def __init__(self) -> None:
        self.commands = []

    async def search(self, command):
        self.commands.append(command)
        return SearchQueryResult(
            query=command.query,
            k=command.k,
            results=[
                SearchResultItem(
                    chunk_id=156,
                    document_id=12,
                    chunk_type="budget_component",
                    content="Backend service implementation with JWT authentication.",
                    distance=0.231,
                    metadata={"scope": "backend"},
                )
            ],
        )


class EmptySearchService:
    async def search(self, command):
        return SearchQueryResult(query=command.query, k=command.k, results=[])


class FailingSearchService:
    async def search(self, command):
        raise RuntimeError("provider exploded with internal details")


def test_search_endpoint_returns_top_k_results(monkeypatch) -> None:
    from app.routers import search as search_router_module

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
            "query": "REST API with OAuth authentication for fintech sector",
            "k": 5,
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert body["query"] == "REST API with OAuth authentication for fintech sector"
    assert body["k"] == 5
    assert isinstance(body["search_time_ms"], int)
    assert body["search_time_ms"] >= 0

    assert body["results"] == [
        {
            "chunk_id": 156,
            "document_id": 12,
            "chunk_type": "budget_component",
            "content": "Backend service implementation with JWT authentication.",
            "distance": 0.231,
            "metadata": {"scope": "backend"},
        }
    ]

    assert len(fake_service.commands) == 1
    assert fake_service.commands[0].query == "REST API with OAuth authentication for fintech sector"
    assert fake_service.commands[0].k == 5


def test_search_endpoint_defaults_k_to_5(monkeypatch) -> None:
    from app.routers import search as search_router_module

    fake_service = FakeSearchService()

    monkeypatch.setattr(
        search_router_module,
        "get_search_service",
        lambda session: fake_service,
    )

    client = TestClient(app)
    response = client.post("/search", json={"query": "OAuth authentication"})

    assert response.status_code == 200
    assert response.json()["k"] == 5
    assert fake_service.commands[0].k == 5


def test_search_endpoint_returns_empty_results(monkeypatch) -> None:
    from app.routers import search as search_router_module

    monkeypatch.setattr(
        search_router_module,
        "get_search_service",
        lambda session: EmptySearchService(),
    )

    client = TestClient(app)
    response = client.post("/search", json={"query": "no matching corpus", "k": 5})

    assert response.status_code == 200
    assert response.json()["results"] == []


def test_search_endpoint_rejects_invalid_k_without_constructing_service(monkeypatch) -> None:
    from app.routers import search as search_router_module

    def fail_if_called(session):
        raise AssertionError("search service should not be constructed for invalid k")

    monkeypatch.setattr(search_router_module, "get_search_service", fail_if_called)

    client = TestClient(app)
    response = client.post("/search", json={"query": "OAuth", "k": 0})

    assert response.status_code == 422


def test_search_endpoint_rejects_blank_query_without_constructing_service(monkeypatch) -> None:
    from app.routers import search as search_router_module

    def fail_if_called(session):
        raise AssertionError("search service should not be constructed for blank query")

    monkeypatch.setattr(search_router_module, "get_search_service", fail_if_called)

    client = TestClient(app)
    response = client.post("/search", json={"query": "   ", "k": 5})

    assert response.status_code == 422


def test_search_endpoint_returns_generic_500_for_service_errors(monkeypatch) -> None:
    from app.routers import search as search_router_module

    monkeypatch.setattr(
        search_router_module,
        "get_search_service",
        lambda session: FailingSearchService(),
    )

    client = TestClient(app)
    response = client.post("/search", json={"query": "OAuth", "k": 5})

    assert response.status_code == 500
    assert response.json() == {"detail": "Semantic search failed"}


def test_search_endpoint_is_registered_in_openapi() -> None:
    client = TestClient(app)

    schema = client.get("/openapi.json").json()

    assert "/search" in schema["paths"]
