from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
QUERY_EXAMPLES = REPO_ROOT / "estimador-cag" / "query_examples.py"


REQUIRED_QUERIES = [
    "REST API development with JWT authentication for financial sector",
    "secure backend service with token-based access control for banking applications",
    "mobile application for restaurant reservations",
    "integration with external system",
    "migration from monolith to microservices architecture using Kubernetes",
]


def test_session08_compose_declares_ai_service() -> None:
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "  ai_service:" in compose
    assert "ghcr.io/astral-sh/uv:python3.11-bookworm" in compose
    assert "working_dir: /workspace/estimador-cag" in compose
    assert "DATABASE_URL=postgresql+asyncpg://estimator:estimator@postgres:5432/estimator" in compose
    assert "OPENAI_API_KEY=${OPENAI_API_KEY:-}" in compose
    assert "app.main:app" in compose
    assert '"8000:8000"' in compose
    assert "condition: service_healthy" in compose


def test_session08_query_examples_script_exists_and_calls_search() -> None:
    assert QUERY_EXAMPLES.is_file()

    script = QUERY_EXAMPLES.read_text(encoding="utf-8")

    assert "/search" in script
    assert "SESSION08_BASE_URL" in script
    assert "argparse" in script
    assert "--dry-run" in script
    assert "urllib.request" in script


def test_session08_query_examples_contains_required_queries() -> None:
    script = QUERY_EXAMPLES.read_text(encoding="utf-8")

    for query in REQUIRED_QUERIES:
        assert query in script


def test_session08_query_examples_documents_required_print_fields() -> None:
    script = QUERY_EXAMPLES.read_text(encoding="utf-8")

    for token in ["chunk_id", "distance", "chunk_type", "content"]:
        assert token in script
