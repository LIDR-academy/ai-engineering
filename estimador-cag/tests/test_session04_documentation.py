from pathlib import Path

HISTORY = Path("docs/HISTORICAL_SESSIONS.md")


def test_historical_doc_preserves_session04_live_plus_architecture() -> None:
    text = HISTORY.read_text(encoding="utf-8")

    required = [
        "Session 04 Live Plus",
        "Structured JSON output",
        "DeepSeek flash → DeepSeek pro → Kimi 2.5 backup → Kimi 2.6 backup_pro",
        "Exact Redis cache runs before semantic cache",
        "Semantic cache shadow mode",
        "requested_tier",
        "served_tier",
        "fallback_used",
        "semantic_cache_mode",
        "semantic_candidate_found",
    ]

    for item in required:
        assert item in text
