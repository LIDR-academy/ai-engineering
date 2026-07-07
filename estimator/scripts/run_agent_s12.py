"""Run the Session 12 manual estimation agent from the command line."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Ensure the estimator package root is on sys.path when invoked as a script.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.config import get_settings  # noqa: E402
from app.generation.agentic.agent_loop import format_trace, run_agent  # noqa: E402
from app.generation.agentic.tool_registry import build_agent_tool_registry  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Session 12 manual estimation agent and print the trace."
    )
    parser.add_argument(
        "transcript",
        type=Path,
        help="Path to a meeting transcript text file.",
    )
    parser.add_argument(
        "--model",
        default="gpt-5",
        help="OpenAI model for the agent loop (default: gpt-5).",
    )
    parser.add_argument(
        "--effort",
        default="medium",
        choices=["minimal", "low", "medium", "high"],
        help="Reasoning effort passed to the Responses API.",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=10,
        help="Maximum tool-loop iterations before max_steps_exceeded.",
    )
    parser.add_argument(
        "--stub",
        action="store_true",
        help="Use the offline reference_retrieval stub instead of pgvector.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional path to write the trace (and summary) as a text file.",
    )
    return parser.parse_args()


async def main() -> int:
    args = parse_args()
    transcript_path = args.transcript
    if not transcript_path.is_file():
        print(f"Transcript not found: {transcript_path}", file=sys.stderr)
        return 1

    transcript = transcript_path.read_text(encoding="utf-8")
    registry = build_agent_tool_registry(use_stub=args.stub)
    settings = get_settings()

    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    result = await run_agent(
        transcript,
        model=args.model,
        effort=args.effort,
        max_steps=args.max_steps,
        tool_registry=registry,
        client=client,
    )

    trace_text = format_trace(result.trace)
    print(trace_text)

    print("--- RESULT ---")
    print(f"status: {result.status}")
    if result.error:
        print(f"error: {result.error}")
    if result.estimate:
        print(json.dumps(result.estimate.model_dump(), indent=2, ensure_ascii=False))
    if result.final_message:
        print("\nfinal_message:")
        print(result.final_message)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        body = trace_text + "\n--- RESULT ---\n"
        body += f"status: {result.status}\n"
        if result.estimate:
            body += json.dumps(result.estimate.model_dump(), indent=2, ensure_ascii=False)
            body += "\n"
        if result.final_message:
            body += f"\nfinal_message:\n{result.final_message}\n"
        args.out.write_text(body, encoding="utf-8")
        print(f"\nTrace written to {args.out}")

    return 0 if result.status == "done" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
