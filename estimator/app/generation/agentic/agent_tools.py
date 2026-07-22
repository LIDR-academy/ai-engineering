"""Tool schemas and deterministic implementations for the Session 12 agent.

``search_budgets`` is wired at runtime via
``tool_registry.build_agent_tool_registry`` so this module never imports RAG.
"""

from __future__ import annotations

import json
import statistics
from typing import Any

from app.generation.agentic.agent_schemas import (
    CalculateEstimateArgs,
    CalculateEstimateResult,
    ComponentBreakdown,
)

# Transparent contingency buffer applied to every component's central estimate.
CONTINGENCY_FACTOR = 0.15

AGENT_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "search_budgets",
        "description": (
            "Search historical project budgets comparable to a single software "
            "component. Call this once per independent component; do not combine "
            "unrelated scopes (for example, an ERP integration and a mobile app) "
            "into one query. Use focused, component-specific language. If results "
            "are weak or empty, reformulate and call again with different terms."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "A focused natural-language description of one component "
                        "to price (e.g. 'SAP ERP integration for billing sync')."
                    ),
                },
                # Strict mode: every property key must be listed in ``required``;
                # optional values use nullable types (OpenAI function-calling guide).
                "filters": {
                    "type": ["object", "null"],
                    "description": "Optional metadata filters to narrow results.",
                    "properties": {
                        "component_type": {
                            "type": ["string", "null"],
                            "enum": [
                                "backend",
                                "integration",
                                "mobile",
                                "analytics",
                                "frontend",
                                "migration",
                                None,
                            ],
                            "description": (
                                "High-level category of the component being priced."
                            ),
                        },
                        "sectors": {
                            "type": ["array", "null"],
                            "items": {"type": "string"},
                            "description": (
                                "Restrict matches to these client sectors "
                                "(e.g. ['logistics', 'industrial'])."
                            ),
                        },
                        "date_range": {
                            "type": ["object", "null"],
                            "properties": {
                                "year_min": {
                                    "type": ["integer", "null"],
                                    "description": "Minimum project year (inclusive).",
                                },
                                "year_max": {
                                    "type": ["integer", "null"],
                                    "description": "Maximum project year (inclusive).",
                                },
                            },
                            "required": ["year_min", "year_max"],
                            "additionalProperties": False,
                        },
                    },
                    "required": ["component_type", "sectors", "date_range"],
                    "additionalProperties": False,
                },
            },
            "required": ["query", "filters"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "calculate_estimate",
        "description": (
            "Compute a partial or total effort estimate deterministically from "
            "components and their historical reference hours gathered via "
            "search_budgets. Call after you have reference_amounts for each "
            "component (use an empty list when no budget was found — the tool "
            "flags unbudgeted components instead of inventing numbers). Does not "
            "call an LLM."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "components": {
                    "type": "array",
                    "description": (
                        "Components to cost, each with historical reference hours."
                    ),
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Human-readable component name.",
                            },
                            "reference_amounts": {
                                "type": "array",
                                "items": {"type": "number"},
                                "description": (
                                    "Historical engineer-hours from search_budgets "
                                    "matches for this component."
                                ),
                            },
                        },
                        "required": ["name", "reference_amounts"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["components"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


async def calculate_estimate(args: dict[str, Any]) -> dict[str, Any]:
    """Cost each component from historical references, then total."""
    parsed = CalculateEstimateArgs.model_validate(args)
    breakdown: list[ComponentBreakdown] = []
    total = 0.0

    for component in parsed.components:
        refs = component.reference_amounts
        if refs:
            central = statistics.median(refs)
            hours = round(central * (1 + CONTINGENCY_FACTOR), 1)
            unbudgeted = False
        else:
            hours = 0.0
            unbudgeted = True

        total += hours
        breakdown.append(
            ComponentBreakdown(
                name=component.name,
                reference_count=len(refs),
                estimated_hours=hours,
                unbudgeted=unbudgeted,
            )
        )

    total = round(total, 1)
    unbudgeted_count = sum(1 for row in breakdown if row.unbudgeted)
    summary = (
        f"total={total}h across {len(breakdown)} components"
        + (f"; {unbudgeted_count} unbudgeted" if unbudgeted_count else "")
    )
    result = CalculateEstimateResult(
        components=breakdown,
        total_hours=total,
        summary=summary,
    )
    return result.model_dump()


def format_action(name: str, args: dict[str, Any]) -> str:
    """Render a tool invocation for the human-readable trace."""
    if name == "search_budgets":
        query = args.get("query", "")
        filters = args.get("filters") or {}
        return f'search_budgets(query="{query}", filters={json.dumps(filters)})'
    if name == "calculate_estimate":
        components = args.get("components", [])
        parts = [
            f"{c.get('name', '?')}{c.get('reference_amounts', [])}"
            for c in components
        ]
        return f"calculate_estimate(components=[{', '.join(parts)}])"
    return f"{name}({json.dumps(args)})"


def format_tool_observation(name: str, result: dict[str, Any]) -> str:
    """Summarise a tool result for the trace observation field."""
    if "error" in result:
        return f"error: {result['error']}"
    if name == "search_budgets":
        return result.get("summary") or format_search_observation(result.get("items", []))
    if name == "calculate_estimate":
        return result.get("summary", json.dumps(result))
    return json.dumps(result, ensure_ascii=False)[:500]


def format_search_observation(items: list[dict[str, Any]]) -> str:
    """Build a compact observation string from search hits."""
    if not items:
        return "0 matches; no historical budgets found"
    hours = [item["estimated_hours"] for item in items if item.get("estimated_hours") is not None]
    hours_str = str(hours) if hours else "[]"
    median = round(statistics.median(hours), 1) if hours else None
    median_part = f"; median={median}h" if median is not None else ""
    closest = items[0].get("distance")
    dist_part = f"; best_distance={closest}" if closest is not None else ""
    return f"{len(items)} matches; hours={hours_str}{median_part}{dist_part}"
