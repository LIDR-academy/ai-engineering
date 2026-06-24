from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit_app


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self.payload


def test_streamlit_search_backend_urls(monkeypatch) -> None:
    monkeypatch.setenv("ESTIMADOR_BACKEND_URL", "https://example.test/")

    assert streamlit_app.build_search_url() == "https://example.test/search"
    assert streamlit_app.build_search_metrics_url() == "https://example.test/search/metrics"


def test_streamlit_post_search_request_uses_backend_search_endpoint(monkeypatch) -> None:
    calls = []

    def fake_post(url, json, timeout):
        calls.append({"url": url, "json": json, "timeout": timeout})
        return FakeResponse(
            {
                "query": json["query"],
                "k": json["k"],
                "search_time_ms": 12,
                "filters_applied": {"client_sector": "finance"},
                "results": [],
            }
        )

    monkeypatch.setenv("ESTIMADOR_BACKEND_URL", "https://backend.test")
    monkeypatch.setattr(streamlit_app.requests, "post", fake_post)

    result = streamlit_app.post_search_request(
        {
            "query": "OAuth backend",
            "k": 5,
            "search_mode": "hybrid",
            "recall_k": 8,
            "client_sector": "finance",
            "client_country": None,
            "tech_stack": "python",
            "scope": "backend",
        }
    )

    assert calls == [
        {
            "url": "https://backend.test/search",
            "json": {
                "query": "OAuth backend",
                "k": 5,
                "search_mode": "hybrid",
                "recall_k": 8,
                "client_sector": "finance",
                "tech_stack": "python",
                "scope": "backend",
            },
            "timeout": (
                streamlit_app.BACKEND_CONNECT_TIMEOUT_SECONDS,
                streamlit_app.BACKEND_READ_TIMEOUT_SECONDS,
            ),
        }
    ]
    assert result["filters_applied"] == {"client_sector": "finance"}


def test_streamlit_get_search_metrics_uses_backend_metrics_endpoint(monkeypatch) -> None:
    calls = []

    def fake_get(url, timeout):
        calls.append({"url": url, "timeout": timeout})
        return FakeResponse(
            {
                "total_searches_recorded": 1,
                "success_count": 1,
                "failure_count": 0,
                "last_search": None,
                "history": [],
            }
        )

    monkeypatch.setenv("ESTIMADOR_BACKEND_URL", "https://backend.test")
    monkeypatch.setattr(streamlit_app.requests, "get", fake_get)

    result = streamlit_app.get_search_metrics()

    assert calls == [
        {
            "url": "https://backend.test/search/metrics",
            "timeout": (
                streamlit_app.BACKEND_CONNECT_TIMEOUT_SECONDS,
                streamlit_app.BACKEND_READ_TIMEOUT_SECONDS,
            ),
        }
    ]
    assert result["total_searches_recorded"] == 1


def test_streamlit_source_contains_session10_retrieval_ui() -> None:
    source = Path("streamlit_app.py").read_text(encoding="utf-8")

    for required in [
        "Session 10 retrieval search",
        "Search historical budgets",
        "search_mode",
        "recall_k",
        "Vector only",
        "Hybrid RRF",
        "client_sector",
        "client_country",
        "tech_stack",
        "scope",
        "Search metrics dashboard",
        "recorded searches",
        "last result count",
        "Recent search history",
        "last_search_metrics",
        "render_search_metrics_dashboard",
        "distance",
        "chunk_type",
        "metadata",
        "post_search_request",
        "get_search_metrics",
    ]:
        assert required in source

    assert "Session 08 semantic search" not in source
