"""Session 12 agent tool registry — wired without pulling the full composition root.

``build_agent_tool_registry`` lives here so ``scripts/run_agent_s12.py`` can
import it without loading tiktoken, SQLAlchemy, or the entire RAG stack. The
composition root re-exports the same factory for FastAPI wiring later.
"""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
from typing import Any

from app.generation.agentic.agent_schemas import SearchBudgetsArgs, ToolFn
from app.generation.agentic.agent_tools import calculate_estimate, format_search_observation

_CONTENT_PREVIEW_MAX = 200
_HISTORICAL_TASK_CHUNK_TYPE = "historical_task"


def _enrich_query(query: str, component_type: str | None) -> str:
    if not component_type:
        return query
    return f"Component type: {component_type}. {query}"


async def search_budgets_impl(args: dict[str, Any]) -> dict[str, Any]:
    """Real ``search_budgets`` backend: embed + hybrid retrieval over task corpus."""
    from app.config import get_settings
    from app.dependencies import get_embedder, get_reranker, get_runtime_retrieval_config
    from app.generation.rag.retrieval.collections import Collection
    from app.generation.rag.retrieval.pipeline import retrieve

    parsed = SearchBudgetsArgs.model_validate(args)
    filters = parsed.filters
    query_text = _enrich_query(
        parsed.query,
        filters.component_type if filters else None,
    )

    embedder = get_embedder()
    if embedder is None:
        return {"error": "Embedding service unavailable (no OPENAI_API_KEY).", "items": []}

    settings = get_settings()
    runtime_retrieval = get_runtime_retrieval_config()
    search_mode = runtime_retrieval.effective_search_mode()
    rerank = runtime_retrieval.effective_rerank()
    # Component-level queries against task-granular chunks sit farther apart than
    # the Session 10 per-task hours search (threshold 0.45). With sector filters
    # the nearest neighbours land around 0.63–0.65, so keep a wider gate.
    top_k = settings.RETRIEVAL_TOP_K
    distance_threshold = max(settings.RETRIEVAL_DISTANCE_THRESHOLD, 0.75)
    recall_k = settings.RETRIEVAL_RECALL_TOP_K
    rerank_top_n = settings.RERANK_TOP_N

    embedding = await asyncio.to_thread(embedder.embed_one, query_text)
    sectors = filters.sectors if filters else None
    year_min = filters.date_range.year_min if filters and filters.date_range else None
    year_max = filters.date_range.year_max if filters and filters.date_range else None

    result = await retrieve(
        query_embedding=embedding,
        query_text=query_text,
        search_mode=search_mode,
        rerank=rerank,
        top_k=top_k,
        recall_k=recall_k,
        rerank_top_n=rerank_top_n if rerank else top_k,
        distance_threshold=distance_threshold,
        rrf_k=settings.RRF_K,
        collection=Collection.BUDGET,
        chunk_types=[_HISTORICAL_TASK_CHUNK_TYPE],
        sectors=sectors,
        project_year_min=year_min,
        project_year_max=year_max,
        reranker=get_reranker() if rerank else None,
    )

    items: list[dict[str, Any]] = []
    for chunk in result.chunks:
        if chunk.estimated_hours is None:
            continue
        preview = chunk.content.replace("\n", " ").strip()
        if len(preview) > _CONTENT_PREVIEW_MAX:
            preview = preview[: _CONTENT_PREVIEW_MAX - 3] + "..."
        items.append(
            {
                "id": chunk.id,
                "content_preview": preview,
                "sector": chunk.sector,
                "budget_id": chunk.budget_id or chunk.source_id or str(chunk.id),
                "estimated_hours": float(chunk.estimated_hours),
                "distance": chunk.distance,
            }
        )

    summary = format_search_observation(items)
    if result.low_confidence:
        summary = f"low confidence — {summary}"

    return {
        "items": items,
        "count": len(items),
        "low_confidence": result.low_confidence,
        "summary": summary,
    }


async def search_budgets_stub_impl(args: dict[str, Any]) -> dict[str, Any]:
    """Offline stub wired from ``exercises/session-12/reference_retrieval.py``."""
    stub_path = (
        Path(__file__).resolve().parents[3] / "exercises" / "session-12" / "reference_retrieval.py"
    )
    spec = importlib.util.spec_from_file_location("reference_retrieval", stub_path)
    if spec is None or spec.loader is None:
        return {"error": f"stub module not found at {stub_path}", "items": []}
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    search_budgets_stub = module.search_budgets_stub

    parsed = SearchBudgetsArgs.model_validate(args)
    filters_dict: dict[str, Any] | None = None
    if parsed.filters:
        filters_dict = parsed.filters.model_dump(exclude_none=True)

    items = search_budgets_stub(parsed.query, filters_dict)
    summary = format_search_observation(items)
    low_confidence = len(items) == 0 or (
        len(items) == 1 and items[0].get("distance", 1.0) > 0.5
    )
    if low_confidence:
        summary = f"low confidence — {summary}"
    return {
        "items": items,
        "count": len(items),
        "low_confidence": low_confidence,
        "summary": summary,
    }


def build_agent_tool_registry(*, use_stub: bool = False) -> dict[str, ToolFn]:
    """Map tool names to async callables for the Session 12 agent loop."""
    search_fn = search_budgets_stub_impl if use_stub else search_budgets_impl
    return {
        "search_budgets": search_fn,
        "calculate_estimate": calculate_estimate,
    }
