from pathlib import Path


def test_session07_live_plus_readiness_doc_exists_and_sets_boundaries() -> None:
    path = Path("docs/session07_live_plus_readiness.md")

    assert path.exists()

    text = path.read_text(encoding="utf-8")

    required_phrases = [
        "Session 07 Live Plus Readiness",
        "What is ready now",
        "What is intentionally deferred",
        "dependency providers",
        "fakeable services",
        "document storage",
        "chunk storage",
        "semantic retrieval",
        "pgvector",
        "No persistence is implemented in this branch",
    ]

    for phrase in required_phrases:
        assert phrase in text
