from fastapi.testclient import TestClient

from app.main import app


def test_search_metrics_endpoint_initial_state() -> None:
    from app.embedding_pipeline.search_metrics import reset_search_metrics

    reset_search_metrics()

    client = TestClient(app)
    response = client.get("/search/metrics")

    assert response.status_code == 200
    body = response.json()

    assert body["total_searches_recorded"] == 0
    assert body["success_count"] == 0
    assert body["failure_count"] == 0
    assert body["last_search"] is None
    assert body["history"] == []


def test_search_metrics_endpoint_records_successful_search(monkeypatch) -> None:
    from app.embedding_pipeline.search_metrics import reset_search_metrics
    from app.embedding_pipeline.search_service import SearchQueryResult, SearchResultItem
    from app.routers import search as search_router_module

    reset_search_metrics()

    class FakeSearchService:
        async def search(self, command):
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
                        metadata={"client_sector": "finance", "scope": "backend"},
                    )
                ],
            )

    monkeypatch.setattr(
        search_router_module,
        "get_search_service",
        lambda session: FakeSearchService(),
    )

    client = TestClient(app)
    search_response = client.post(
        "/search",
        json={
            "query": "OAuth backend",
            "k": 3,
            "client_sector": "finance",
            "scope": "backend",
        },
    )

    assert search_response.status_code == 200

    metrics_response = client.get("/search/metrics")

    assert metrics_response.status_code == 200
    metrics = metrics_response.json()

    assert metrics["total_searches_recorded"] == 1
    assert metrics["success_count"] == 1
    assert metrics["failure_count"] == 0
    assert metrics["last_search"]["query"] == "OAuth backend"
    assert metrics["last_search"]["k"] == 3
    assert metrics["last_search"]["result_count"] == 1
    assert metrics["last_search"]["status"] == "success"
    assert metrics["last_search"]["filters_applied"] == {
        "client_sector": "finance",
        "scope": "backend",
    }
    assert metrics["last_search"]["search_time_ms"] >= 0
    assert metrics["history"][0] == metrics["last_search"]


def test_search_metrics_endpoint_records_failed_search(monkeypatch) -> None:
    from app.embedding_pipeline.search_metrics import reset_search_metrics
    from app.routers import search as search_router_module

    reset_search_metrics()

    class FailingSearchService:
        async def search(self, command):
            raise RuntimeError("database unavailable")

    monkeypatch.setattr(
        search_router_module,
        "get_search_service",
        lambda session: FailingSearchService(),
    )

    client = TestClient(app)
    search_response = client.post(
        "/search",
        json={
            "query": "OAuth backend",
            "k": 3,
        },
    )

    assert search_response.status_code == 500

    metrics = client.get("/search/metrics").json()

    assert metrics["total_searches_recorded"] == 1
    assert metrics["success_count"] == 0
    assert metrics["failure_count"] == 1
    assert metrics["last_search"]["query"] == "OAuth backend"
    assert metrics["last_search"]["status"] == "failure"
    assert metrics["last_search"]["error_type"] == "RuntimeError"
    assert metrics["last_search"]["result_count"] == 0


def test_session08_browser_demo_exposes_search_metrics_dashboard() -> None:
    html = (
        __import__("pathlib")
        .Path("docs/session08_search_demo.html")
        .read_text(encoding="utf-8")
    )

    assert "Search metrics dashboard" in html
    assert "/search/metrics" in html
    assert "loadSearchMetrics" in html
