"""Manual agent loop over the OpenAI Responses API (Session 12).

The loop is driven explicitly: each ``function_call`` is executed locally and
returned as ``function_call_output`` with the matching ``call_id``. No framework
or hidden agentic chaining.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Literal

import structlog
from openai import AsyncOpenAI

from app.generation.agentic.agent_schemas import (
    AgentEstimate,
    AgentResult,
    AgentStep,
    ComponentEstimate,
    ToolFn,
)
from app.generation.agentic.agent_tools import (
    AGENT_TOOLS,
    format_action,
    format_tool_observation,
)

log = structlog.get_logger()

DEFAULT_MAX_STEPS = 10

SYSTEM_PROMPT = (
    "You are a software estimation agent. Given a meeting transcript:\n"
    "1. Identify every independent component that must be estimated.\n"
    "2. Call search_budgets once per component with a focused query. Never "
    "combine unrelated components in a single search.\n"
    "3. If a search returns low confidence or no matches, reformulate and "
    "search again before moving on.\n"
    "4. When you have reference hours for each component, call "
    "calculate_estimate with reference_amounts taken from the search results.\n"
    "5. Produce a concise final answer summarising the structured estimate "
    "(component names, hours per component, total hours, and any unbudgeted "
    "flags or assumptions).\n"
    "Use the tools for all retrieval and costing — do not invent historical "
    "reference numbers."
)

ReasoningEffort = Literal["minimal", "low", "medium", "high"]


def _extract_reasoning(output: list[Any]) -> str:
    """Collect reasoning summaries from a Responses API output list."""
    parts: list[str] = []
    for item in output:
        item_type = getattr(item, "type", None)
        if item_type == "reasoning":
            summary = getattr(item, "summary", None)
            if summary:
                if isinstance(summary, list):
                    for block in summary:
                        text = getattr(block, "text", None) or (
                            block.get("text") if isinstance(block, dict) else None
                        )
                        if text:
                            parts.append(text)
                elif isinstance(summary, str):
                    parts.append(summary)
            content = getattr(item, "content", None)
            if content and isinstance(content, str):
                parts.append(content)
        if item_type == "message":
            for block in getattr(item, "content", []) or []:
                block_type = getattr(block, "type", None)
                if block_type == "reasoning" or block_type == "reasoning_text":
                    text = getattr(block, "text", None)
                    if text:
                        parts.append(text)
    return " ".join(parts).strip() or "—"


def _extract_function_calls(output: list[Any]) -> list[Any]:
    return [item for item in output if getattr(item, "type", None) == "function_call"]


def _extract_final_message(output: list[Any]) -> str | None:
    for item in reversed(output):
        if getattr(item, "type", None) != "message":
            continue
        texts: list[str] = []
        for block in getattr(item, "content", []) or []:
            if getattr(block, "type", None) == "output_text":
                text = getattr(block, "text", None)
                if text:
                    texts.append(text)
        if texts:
            return "\n".join(texts)
    return None


async def execute_tool(
    registry: dict[str, ToolFn],
    name: str,
    args: dict[str, Any],
) -> dict[str, Any]:
    """Dispatch a tool call; failures become observations, not crashes."""
    fn = registry.get(name)
    if fn is None:
        return {"error": f"unknown tool: {name}"}
    try:
        return await fn(args)
    except Exception as exc:  # noqa: BLE001 — tool errors must not kill the loop
        log.warning("agent_tool_failed", tool=name, error=str(exc))
        return {"error": str(exc)}


def _estimate_from_calculate(result: dict[str, Any]) -> AgentEstimate:
    components = [
        ComponentEstimate(
            name=row["name"],
            estimated_hours=row["estimated_hours"],
            unbudgeted=row.get("unbudgeted", False),
        )
        for row in result.get("components", [])
    ]
    return AgentEstimate(
        components=components,
        total_hours=result.get("total_hours", 0.0),
        notes=result.get("summary", ""),
    )


def format_trace(trace: list[AgentStep]) -> str:
    """Render the step-by-step trace in the deliverable format."""
    lines: list[str] = []
    for step in trace:
        lines.append(f"STEP {step.step}")
        lines.append(f"  reasoning:   {step.reasoning}")
        lines.append(f"  action:      {step.action}")
        lines.append(f"  observation: {step.observation}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


async def run_agent(
    transcript: str,
    *,
    model: str = "gpt-5",
    effort: ReasoningEffort = "medium",
    max_steps: int = DEFAULT_MAX_STEPS,
    tool_registry: dict[str, ToolFn],
    client: AsyncOpenAI | None = None,
) -> AgentResult:
    """Run the manual estimation agent and return a structured result + trace."""
    if client is None:
        client = AsyncOpenAI()

    trace: list[AgentStep] = []
    last_calculate: dict[str, Any] | None = None
    step_number = 0
    converged = False
    final_message: str | None = None

    try:
        response = await client.responses.create(
            model=model,
            reasoning={"effort": effort},
            instructions=SYSTEM_PROMPT,
            input=[{"role": "user", "content": transcript}],
            tools=AGENT_TOOLS,
        )
    except Exception as exc:  # noqa: BLE001
        return AgentResult(status="error", error=str(exc), trace=trace)

    for _ in range(max_steps):
        calls = _extract_function_calls(response.output)
        reasoning = _extract_reasoning(response.output)

        if not calls:
            converged = True
            final_message = _extract_final_message(response.output)
            break

        results = await asyncio.gather(
            *(
                execute_tool(
                    tool_registry,
                    call.name,
                    json.loads(call.arguments),
                )
                for call in calls
            )
        )

        tool_outputs: list[dict[str, Any]] = []
        for call, result in zip(calls, results, strict=True):
            step_number += 1
            args = json.loads(call.arguments)
            if call.name == "calculate_estimate":
                last_calculate = result

            trace.append(
                AgentStep(
                    step=step_number,
                    reasoning=reasoning,
                    action=format_action(call.name, args),
                    observation=format_tool_observation(call.name, result),
                )
            )
            tool_outputs.append(
                {
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": json.dumps(result),
                }
            )

        try:
            response = await client.responses.create(
                model=model,
                reasoning={"effort": effort},
                previous_response_id=response.id,
                instructions=SYSTEM_PROMPT,
                input=tool_outputs,
                tools=AGENT_TOOLS,
            )
        except Exception as exc:  # noqa: BLE001
            return AgentResult(status="error", error=str(exc), trace=trace)

    if not converged:
        return AgentResult(status="max_steps_exceeded", trace=trace)

    estimate: AgentEstimate | None = None
    if last_calculate and "error" not in last_calculate:
        estimate = _estimate_from_calculate(last_calculate)
    elif final_message:
        estimate = AgentEstimate(
            components=[],
            total_hours=0.0,
            notes=final_message,
        )

    return AgentResult(
        status="done",
        estimate=estimate,
        trace=trace,
        final_message=final_message,
    )
