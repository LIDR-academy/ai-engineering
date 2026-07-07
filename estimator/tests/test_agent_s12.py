"""Tests for the Session 12 manual estimation agent (no live LLM calls)."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.generation.agentic.agent_loop import format_trace, run_agent
from app.generation.agentic.agent_tools import calculate_estimate
from app.generation.agentic.tool_registry import build_agent_tool_registry


def _function_call(call_id: str, name: str, arguments: dict) -> SimpleNamespace:
    return SimpleNamespace(
        type="function_call",
        call_id=call_id,
        name=name,
        arguments=json.dumps(arguments),
    )


def _reasoning(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="reasoning", summary=text, content=None)


def _message(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        type="message",
        content=[SimpleNamespace(type="output_text", text=text)],
    )


def _response(response_id: str, output: list) -> SimpleNamespace:
    return SimpleNamespace(id=response_id, output=output)


@pytest.mark.asyncio
async def test_calculate_estimate_median_and_contingency():
    result = await calculate_estimate(
        {
            "components": [
                {"name": "Auth backend", "reference_amounts": [420.0, 380.0]},
                {"name": "Mobile app", "reference_amounts": [780.0, 640.0]},
            ]
        }
    )
    assert result["total_hours"] == round(400.0 * 1.15 + 710.0 * 1.15, 1)
    assert all(not row["unbudgeted"] for row in result["components"])


@pytest.mark.asyncio
async def test_calculate_estimate_flags_unbudgeted():
    result = await calculate_estimate(
        {"components": [{"name": "Unknown", "reference_amounts": []}]}
    )
    assert result["components"][0]["unbudgeted"] is True
    assert result["components"][0]["estimated_hours"] == 0.0


@pytest.mark.asyncio
async def test_agent_loop_complex_transcript_mocked():
    """Simulate multi-component flow: 4 searches + calculate + final message."""
    registry = build_agent_tool_registry(use_stub=True)

    responses = [
        _response(
            "resp-1",
            [
                _reasoning("Four independent components; search each separately."),
                _function_call("c1", "search_budgets", {"query": "business backend API orders routes"}),
                _function_call("c2", "search_budgets", {"query": "SAP ERP integration billing"}),
                _function_call("c3", "search_budgets", {"query": "mobile delivery app offline sync"}),
                _function_call("c4", "search_budgets", {"query": "analytics KPI dashboard alerts"}),
            ],
        ),
        _response(
            "resp-2",
            [
                _reasoning("References gathered; consolidate deterministically."),
                _function_call(
                    "c5",
                    "calculate_estimate",
                    {
                        "components": [
                            {"name": "Core backend", "reference_amounts": [1150.0, 940.0]},
                            {"name": "SAP integration", "reference_amounts": [860.0, 720.0]},
                            {"name": "Mobile app", "reference_amounts": [780.0, 640.0]},
                            {"name": "Analytics panel", "reference_amounts": [560.0, 430.0]},
                        ]
                    },
                ),
            ],
        ),
        _response(
            "resp-3",
            [
                _reasoning("Estimate ready to present."),
                _message("Total effort estimated across four components."),
            ],
        ),
    ]

    client = MagicMock()
    client.responses = MagicMock()
    client.responses.create = AsyncMock(side_effect=responses)

    transcript = (  # minimal stand-in for the complex file
        "backend API, SAP ERP integration, mobile offline app, analytics KPI dashboard"
    )
    result = await run_agent(
        transcript,
        model="gpt-5",
        effort="medium",
        max_steps=10,
        tool_registry=registry,
        client=client,
    )

    assert result.status == "done"
    assert result.estimate is not None
    assert len(result.estimate.components) == 4
    assert result.estimate.total_hours > 0

    search_steps = [s for s in result.trace if s.action.startswith("search_budgets")]
    calc_steps = [s for s in result.trace if s.action.startswith("calculate_estimate")]
    assert len(search_steps) >= 2
    assert len(calc_steps) == 1

    for step in result.trace:
        assert step.reasoning
        assert step.action
        assert step.observation

    trace_text = format_trace(result.trace)
    assert "STEP 1" in trace_text
    assert "search_budgets" in trace_text
    assert "calculate_estimate" in trace_text


@pytest.mark.asyncio
async def test_agent_loop_max_steps_guard():
    registry = build_agent_tool_registry(use_stub=True)

    endless = _response(
        "resp-loop",
        [
            _reasoning("Keep searching."),
            _function_call("c1", "search_budgets", {"query": "backend"}),
        ],
    )
    client = MagicMock()
    client.responses = MagicMock()
    client.responses.create = AsyncMock(return_value=endless)

    result = await run_agent(
        "backend only",
        max_steps=2,
        tool_registry=registry,
        client=client,
    )
    assert result.status == "max_steps_exceeded"
    assert len(result.trace) == 2
