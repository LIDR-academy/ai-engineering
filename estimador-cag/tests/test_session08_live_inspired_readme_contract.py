from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HISTORY = REPO_ROOT / "docs" / "HISTORICAL_SESSIONS.md"


def _history() -> str:
    return HISTORY.read_text(encoding="utf-8")


def test_historical_doc_preserves_session08_learning_context() -> None:
    text = _history()

    assert "Session 08 pgvector semantic search baseline" in text
    assert "PostgreSQL plus pgvector retrieval" in text
    assert "query_examples.py" in text
    assert "output_examples.txt" in text


def test_historical_doc_preserves_session06_and_session07_context() -> None:
    text = _history()

    assert "Session 06 CAG stress baseline" in text
    assert "Session 07 embedding and chunking work" in text
    assert "DeepSeek" in text
