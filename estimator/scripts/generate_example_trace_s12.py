"""Generate an example Session 12 trace offline (stub retrieval + mocked LLM).

Use when live OpenAI calls are unavailable. The tool executions are real; only
the model decisions are scripted to match the complex transcript structure.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.generation.agentic.agent_loop import format_trace, run_agent  # noqa: E402
from app.generation.agentic.tool_registry import build_agent_tool_registry  # noqa: E402


def _fc(call_id: str, name: str, arguments: dict) -> SimpleNamespace:
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


def _resp(rid: str, output: list) -> SimpleNamespace:
    return SimpleNamespace(id=rid, output=output)


async def main() -> int:
    transcript_path = _ROOT / "exercises" / "session-12" / "sample_transcript_complex.txt"
    out_path = _ROOT / "exercises" / "session-12" / "example_trace_complex.txt"
    transcript = transcript_path.read_text(encoding="utf-8")
    registry = build_agent_tool_registry(use_stub=True)

    # Scripted model trajectory for the four RUTA components.
    responses = [
        _resp(
            "r1",
            [
                _reasoning(
                    "The transcript names four independent scopes: core business "
                    "backend, SAP ERP integration, offline mobile app, and an "
                    "analytics dashboard. I will search historical budgets for "
                    "each one separately."
                ),
                _fc(
                    "s1",
                    "search_budgets",
                    {
                        "query": "business backend API orders routes tariffs tracking",
                        "filters": {"component_type": "backend", "sectors": ["logistics"]},
                    },
                ),
                _fc(
                    "s2",
                    "search_budgets",
                    {
                        "query": "SAP ERP integration billing customers articles IDocs middleware",
                        "filters": {"component_type": "integration", "sectors": ["industrial"]},
                    },
                ),
                _fc(
                    "s3",
                    "search_budgets",
                    {
                        "query": "mobile delivery app Android iOS offline sync signature photo",
                        "filters": {"component_type": "mobile", "sectors": ["logistics"]},
                    },
                ),
                _fc(
                    "s4",
                    "search_budgets",
                    {
                        "query": "analytics KPI dashboard on-time delivery route costs alerts",
                        "filters": {"component_type": "analytics", "sectors": ["logistics"]},
                    },
                ),
            ],
        ),
        _resp(
            "r2",
            [
                _reasoning(
                    "Each component has comparable historical references. I will "
                    "consolidate them deterministically with calculate_estimate."
                ),
                _fc(
                    "c1",
                    "calculate_estimate",
                    {
                        "components": [
                            {
                                "name": "Core business backend",
                                "reference_amounts": [1150.0, 940.0],
                            },
                            {
                                "name": "SAP ERP integration",
                                "reference_amounts": [860.0, 720.0],
                            },
                            {
                                "name": "Mobile delivery app",
                                "reference_amounts": [780.0, 640.0],
                            },
                            {
                                "name": "Analytics dashboard",
                                "reference_amounts": [560.0, 430.0],
                            },
                        ]
                    },
                ),
            ],
        ),
        _resp(
            "r3",
            [
                _reasoning("The consolidated estimate is ready to present."),
                _message(
                    "Estimated effort for RUTA across four components: core backend, "
                    "SAP integration, mobile app, and analytics dashboard. See structured "
                    "breakdown from calculate_estimate."
                ),
            ],
        ),
    ]

    client = MagicMock()
    client.responses = MagicMock()
    client.responses.create = AsyncMock(side_effect=responses)

    result = await run_agent(
        transcript,
        model="gpt-5",
        effort="medium",
        max_steps=10,
        tool_registry=registry,
        client=client,
    )

    trace_text = format_trace(result.trace)
    body = trace_text + "\n--- RESULT ---\n"
    body += f"status: {result.status}\n"
    if result.estimate:
        body += json.dumps(result.estimate.model_dump(), indent=2, ensure_ascii=False)
        body += "\n"

    out_path.write_text(body, encoding="utf-8")
    print(body)
    print(f"Written to {out_path}")
    return 0 if result.status == "done" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
