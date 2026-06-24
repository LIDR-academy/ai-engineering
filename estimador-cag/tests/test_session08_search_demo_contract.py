from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO = PROJECT_ROOT / "docs" / "session08_search_demo.html"


def test_session08_search_demo_file_exists_and_targets_search_api() -> None:
    assert DEMO.is_file()

    html = DEMO.read_text(encoding="utf-8")

    assert "Session 08 pgvector search demo" in html
    assert "/embeddings/ingest" in html
    assert "/search" in html
    assert "Document already ingested" in html
    assert "REST API development with JWT authentication for financial sector" in html
    assert "migration from monolith to microservices architecture using Kubernetes" in html
    assert "/api/v1/estimate" not in html
    assert "/api/v1/estimate/stream" not in html


def test_root_and_demo_routes_serve_session08_search_demo() -> None:
    client = TestClient(app)

    for route in ["/", "/demo"]:
        response = client.get(route)

        assert response.status_code == 200
        assert "Session 08 pgvector search demo" in response.text
        assert "/search" in response.text
        assert "/api/v1/estimate" not in response.text


def test_legacy_sse_demo_is_still_available_at_sse_demo() -> None:
    client = TestClient(app)

    response = client.get("/sse-demo")

    assert response.status_code == 200
    assert "Synchronous response vs SSE streaming" in response.text
    assert "/api/v1/estimate" in response.text
