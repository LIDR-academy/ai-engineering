"""
LAYER: tests
RESPONSIBILITY: Verify that the FastAPI application boots correctly
WHY IT EXISTS: Automated testing prevents regressions when refactoring.
DEPENDS ON: app.main (FastAPI app)
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint():
    """Test automatizado del endpoint /health. Corre con: uv run pytest tests/ -v"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
