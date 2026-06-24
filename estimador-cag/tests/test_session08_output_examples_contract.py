from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_EXAMPLES = REPO_ROOT / "estimador-cag" / "output_examples.txt"

REQUIRED_QUERY_HEADERS = [
    "Query 1: REST API development with JWT authentication for financial sector",
    "Query 2: secure backend service with token-based access control for banking applications",
    "Query 3: mobile application for restaurant reservations",
    "Query 4: integration with external system",
    "Query 5: migration from monolith to microservices architecture using Kubernetes",
]


def test_session08_output_examples_file_exists() -> None:
    assert OUTPUT_EXAMPLES.is_file()


def test_session08_output_examples_contains_all_required_queries() -> None:
    output = OUTPUT_EXAMPLES.read_text(encoding="utf-8")

    for query_header in REQUIRED_QUERY_HEADERS:
        assert query_header in output


def test_session08_output_examples_contains_real_search_result_fields() -> None:
    output = OUTPUT_EXAMPLES.read_text(encoding="utf-8")

    assert "Server search_time_ms:" in output
    assert "Results returned:" in output
    assert "chunk_id=" in output
    assert "distance=" in output
    assert "chunk_type=" in output
    assert "metadata=" in output
