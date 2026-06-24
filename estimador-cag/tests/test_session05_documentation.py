from pathlib import Path

HISTORY = Path("docs/HISTORICAL_SESSIONS.md")


def _history() -> str:
    return HISTORY.read_text(encoding="utf-8")


def test_historical_doc_preserves_session05_memory_and_attachment_flow() -> None:
    text = _history()

    required = [
        "Session 05",
        "POST /sessions",
        "POST /sessions/{session_id}/estimate",
        "multipart/form-data",
        "PDF",
        "DOCX",
        "ConversationHistory",
        "ProjectMetadata",
        "SessionStore",
        "sliding window",
        "project_metadata",
    ]

    for item in required:
        assert item in text


def test_historical_doc_preserves_streamlit_session05_usage() -> None:
    text = _history()

    required = [
        "New conversation",
        "session_id",
        "sidebar",
        "Project metadata",
    ]

    for item in required:
        assert item in text
