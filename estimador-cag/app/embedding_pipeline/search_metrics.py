"""
LAYER: search observability
RESPONSIBILITY: Keep a small rolling in-memory dashboard for semantic search calls.
WHY IT EXISTS: Session 08 extra-mile work needs measurable retrieval behavior before
               adding vector indexes or tuning.
"""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

_MAX_HISTORY = 100

_search_history: deque[SearchMetricRecord] = deque(maxlen=_MAX_HISTORY)
_success_count = 0
_failure_count = 0


@dataclass(frozen=True)
class SearchMetricRecord:
    """One semantic search metric entry."""

    query: str
    k: int
    filters_applied: dict[str, Any]
    result_count: int
    search_time_ms: int
    status: str
    error_type: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


def reset_search_metrics() -> None:
    """Reset metrics for deterministic tests."""
    global _success_count, _failure_count
    _search_history.clear()
    _success_count = 0
    _failure_count = 0


def record_search_success(
    *,
    query: str,
    k: int,
    filters_applied: dict[str, Any],
    result_count: int,
    search_time_ms: int,
) -> None:
    """Record one successful semantic search."""
    global _success_count
    _success_count += 1
    _search_history.append(
        SearchMetricRecord(
            query=query,
            k=k,
            filters_applied=filters_applied,
            result_count=result_count,
            search_time_ms=search_time_ms,
            status="success",
        )
    )


def record_search_failure(
    *,
    query: str,
    k: int,
    filters_applied: dict[str, Any],
    search_time_ms: int,
    error_type: str,
) -> None:
    """Record one failed semantic search."""
    global _failure_count
    _failure_count += 1
    _search_history.append(
        SearchMetricRecord(
            query=query,
            k=k,
            filters_applied=filters_applied,
            result_count=0,
            search_time_ms=search_time_ms,
            status="failure",
            error_type=error_type,
        )
    )


def get_search_metrics_dashboard() -> dict[str, Any]:
    """Return a dashboard-friendly snapshot of recent search behavior."""
    history = [asdict(item) for item in _search_history]
    return {
        "total_searches_recorded": len(history),
        "success_count": _success_count,
        "failure_count": _failure_count,
        "last_search": history[-1] if history else None,
        "history": history,
    }
