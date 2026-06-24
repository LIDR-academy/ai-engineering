from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ROOT_README = REPO_ROOT / "README.md"


def _readme() -> str:
    return ROOT_README.read_text(encoding="utf-8")


def test_root_readme_documents_current_session10_submission() -> None:
    text = _readme()

    assert "gg-session-10/pre-work" in text
    assert "Session 10 — advanced retrieval compass and A/B/C/D retrieval evaluation" in text
    assert "estimador-cag/" in text
    assert "gg-session-08-pgvector-search" not in text


def test_root_readme_documents_session10_measurement_runner() -> None:
    text = _readme()

    assert "uv run python -m evals.session10_retrieval.run" in text
    assert "evals/session10_retrieval/results.json" in text
    assert "evals/session10_retrieval/REPORT.md" in text
    assert "A/B/C/D retrieval variants" in text


def test_root_readme_documents_bounded_interpretation() -> None:
    text = _readme()

    assert "wiring and smoke evidence" in text
    assert "not proof that hybrid search or reranking improves quality in production" in text
    assert "result budget precision@5" in text
    assert "unique budget precision@5" in text


def test_root_readme_documents_provider_policy_and_security() -> None:
    text = _readme()

    assert "prefer DeepSeek first" in text
    assert "Kimi only as fallback or comparison" in text
    assert "Do not commit `.env`, real API keys" in text
