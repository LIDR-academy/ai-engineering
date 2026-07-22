"""One-shot static checks for S12 verification (safe to delete after)."""

from __future__ import annotations

import asyncio
import ast
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.generation.agentic.agent_tools import AGENT_TOOLS, calculate_estimate
from app.generation.agentic.tool_registry import build_agent_tool_registry


def main() -> None:
    print("=== STATIC ===")
    print("AGENT_TOOLS:", [t["name"] for t in AGENT_TOOLS])
    print("strict:", all(t.get("strict") is True for t in AGENT_TOOLS))
    print("flat schema keys:", sorted(AGENT_TOOLS[0].keys()))
    print("registry stub:", sorted(build_agent_tool_registry(use_stub=True)))

    tools_path = _ROOT / "app/generation/agentic/agent_tools.py"
    tree = ast.parse(tools_path.read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
        elif isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
    print("agent_tools top-level imports:", imports)
    print("agent_tools imports rag?", any("rag" in i for i in imports))

    loop_src = (_ROOT / "app/generation/agentic/agent_loop.py").read_text(encoding="utf-8")
    print("has MAX/DEFAULT_MAX_STEPS:", "DEFAULT_MAX_STEPS" in loop_src)
    print("uses previous_response_id:", "previous_response_id" in loop_src)
    print("uses asyncio.gather:", "asyncio.gather" in loop_src)
    print("function_call_output:", "function_call_output" in loop_src)

    async def calc_check() -> tuple[float, float]:
        r = await calculate_estimate(
            {
                "components": [
                    {"name": "Core business backend", "reference_amounts": [1150.0, 940.0]},
                    {"name": "SAP ERP integration", "reference_amounts": [860.0, 720.0]},
                    {"name": "Mobile delivery app", "reference_amounts": [780.0, 640.0]},
                    {"name": "Analytics dashboard", "reference_amounts": [560.0, 430.0]},
                ]
            }
        )
        print("calc 2-refs-each total:", r["total_hours"], r["summary"])
        r2 = await calculate_estimate(
            {
                "components": [
                    {"name": "Core business backend", "reference_amounts": [1150.0, 940.0]},
                    {"name": "SAP ERP integration", "reference_amounts": [860.0, 720.0]},
                    {"name": "Mobile delivery app", "reference_amounts": [780.0]},
                    {"name": "Analytics dashboard", "reference_amounts": [560.0]},
                ]
            }
        )
        print(
            "calc matching single-hit obs:",
            r2["total_hours"],
            [(c["name"], c["estimated_hours"]) for c in r2["components"]],
        )
        return float(r["total_hours"]), float(r2["total_hours"])

    two_ref_total, one_ref_total = asyncio.run(calc_check())

    trace_path = _ROOT / "exercises/session-12/example_trace_complex.txt"
    text = trace_path.read_text(encoding="utf-8")
    searches = re.findall(r'action:\s+search_budgets\(query="([^"]+)"', text)
    calcs = re.findall(r"action:\s+calculate_estimate\([^\n]+\)", text)
    print("=== EXISTING example_trace_complex.txt ===")
    print("search_budgets calls:", len(searches))
    for query in searches:
        print(" -", query[:100])
    print("calculate_estimate calls:", len(calcs))
    print("status done?", "status: done" in text)

    body, _, result = text.partition("--- RESULT ---")
    step_blocks = [b for b in re.split(r"\n(?=STEP \d+)", body.strip()) if b.startswith("STEP")]
    incomplete = []
    for block in step_blocks:
        if not all(k in block for k in ("reasoning:", "action:", "observation:")):
            incomplete.append(block.splitlines()[0])
    print("steps:", len(step_blocks), "incomplete:", incomplete or "none")

    total_m = re.search(r'"total_hours":\s*([\d.]+)', result)
    comps = re.findall(r'"estimated_hours":\s*([\d.]+)', result)
    total = float(total_m.group(1)) if total_m else None
    if total is not None and comps:
        summed = round(sum(float(x) for x in comps), 1)
        print(
            f"total_hours={total}, sum(components)={summed}, "
            f"coherent={abs(total - summed) < 0.2}, n_components={len(comps)}"
        )
        print(
            "example matches 2-ref contingency math:",
            abs(total - two_ref_total) < 0.2,
            f"(two_ref={two_ref_total}, one_ref={one_ref_total})",
        )


if __name__ == "__main__":
    main()
