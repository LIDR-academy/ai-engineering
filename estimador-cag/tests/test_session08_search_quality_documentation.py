from pathlib import Path

HISTORY = Path("docs/HISTORICAL_SESSIONS.md")


def _history() -> str:
    return HISTORY.read_text(encoding="utf-8")


def test_historical_doc_documents_session08_search_quality_workflow() -> None:
    text = _history()

    assert "Session 08 search-quality evaluation workflow" in text
    assert "evals/session08_search_quality/cases.jsonl" in text
    assert "evals/session08_search_quality/evaluator.py" in text
    assert "evals/session08_search_quality/capture.py" in text
    assert "uv run python -m evals.session08_search_quality.capture" in text
    assert "uv run python -m evals.session08_search_quality.evaluator" in text


def test_historical_doc_documents_search_quality_safety_boundaries() -> None:
    text = _history()

    assert "No LLM judge" in text
    assert "No live provider call in tests" in text
    assert "No benchmark superiority claim" in text
    assert "Captured responses should be reviewed before committing" in text


def test_historical_doc_documents_capture_dry_run_before_live_capture() -> None:
    text = _history()

    dry_run_index = text.index("--dry-run")
    live_capture_index = text.index("--base-url http://localhost:8000")
    assert dry_run_index < live_capture_index
