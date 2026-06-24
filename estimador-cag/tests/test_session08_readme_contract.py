from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
README = REPO_ROOT / "estimador-cag" / "README.md"


def _readme() -> str:
    return README.read_text(encoding="utf-8")


def test_project_readme_documents_current_session10_branch_and_stack() -> None:
    text = _readme()

    assert "gg-session-10/pre-work" in text
    assert "Session 10 — advanced retrieval compass" in text
    assert "app/embedding_pipeline/fusion.py" in text
    assert "app/embedding_pipeline/reranker.py" in text
    assert "POST /search" in text


def test_project_readme_documents_abcd_retrieval_evaluation() -> None:
    text = _readme()

    assert "| A | Vector | No |" in text
    assert "| B | Hybrid | No |" in text
    assert "| C | Vector | Yes |" in text
    assert "| D | Hybrid | Yes |" in text
    assert "uv run python -m evals.session10_retrieval.run" in text


def test_project_readme_explains_metric_interpretation_and_limitations() -> None:
    text = _readme()

    assert "result budget precision@5" in text
    assert "unique budget precision@5" in text
    assert "corpus has only four budgets, eight component chunks, and seven clean queries" in text
    assert "does not prove hybrid retrieval or reranking superiority" in text


def test_project_readme_documents_validation_provider_policy_and_history() -> None:
    text = _readme()

    assert "OPENAI_API_KEY=test DEEPSEEK_API_KEY=test KIMI_API_KEY=test uv run pytest -q" in text
    assert "prefer DeepSeek first" in text
    assert "Kimi only as fallback or comparison" in text
    assert "docs/HISTORICAL_SESSIONS.md" in text
