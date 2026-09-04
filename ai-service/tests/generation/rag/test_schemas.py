"""Unit tests for standalone RAG schema behaviour (no network, no DB)."""

from __future__ import annotations

from app.generation.rag.schemas import TaskNeighbor


def test_task_neighbor_source_id_is_optional():
    # An agent-derived analog may not carry a corpus chunk id (see
    # DeriveTaskHoursNeighbor.source_id in generation/agentic/agent_schemas.py).
    neighbor = TaskNeighbor(estimated_hours=40, distance=0.2)
    assert neighbor.source_id is None
    assert neighbor.model_dump()["source_id"] is None


def test_task_neighbor_source_id_still_accepts_an_int():
    neighbor = TaskNeighbor(source_id=7, estimated_hours=40, distance=0.2)
    assert neighbor.source_id == 7
