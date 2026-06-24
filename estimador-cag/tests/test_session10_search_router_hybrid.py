from fastapi.testclient import TestClient

from app.embedding_pipeline.search_service import SearchQueryResult
from app.main import app
from app.routers import search as search_router


class CapturingSearchService:
    def __init__(self) -> None:
        self.commands = []

    async def search(self, command):
        self.commands.append(command)
        return SearchQueryResult(
            query=command.query,
            k=command.k,
            filters_applied=command.metadata_filters.as_response_dict(),
            results=[],
        )


def test_search_endpoint_forwards_hybrid_search_options(monkeypatch):
    service = CapturingSearchService()

    monkeypatch.setattr(
        search_router,
        "get_search_service",
        lambda session: service,
    )

    client = TestClient(app)
    response = client.post(
        "/search",
        json={
            "query": "OAuth banking authentication",
            "k": 5,
            "search_mode": "hybrid",
            "recall_k": 10,
        },
    )

    assert response.status_code == 200
    assert response.json()["results"] == []

    assert len(service.commands) == 1
    command = service.commands[0]
    assert command.query == "OAuth banking authentication"
    assert command.k == 5
    assert command.search_mode == "hybrid"
    assert command.recall_k == 10


def test_search_endpoint_defaults_to_vector_mode(monkeypatch):
    service = CapturingSearchService()

    monkeypatch.setattr(
        search_router,
        "get_search_service",
        lambda session: service,
    )

    client = TestClient(app)
    response = client.post(
        "/search",
        json={
            "query": "OAuth banking authentication",
        },
    )

    assert response.status_code == 200

    command = service.commands[0]
    assert command.search_mode == "vector"
    assert command.recall_k == 50


def test_search_endpoint_rejects_invalid_search_mode_without_constructing_service(
    monkeypatch,
):
    def fail_if_called(session):
        raise AssertionError("search service should not be constructed")

    monkeypatch.setattr(search_router, "get_search_service", fail_if_called)

    client = TestClient(app)
    response = client.post(
        "/search",
        json={
            "query": "OAuth banking authentication",
            "search_mode": "invalid_mode",
        },
    )

    assert response.status_code == 422
