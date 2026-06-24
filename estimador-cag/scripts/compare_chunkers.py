"""
CLI lab for Session 07 chunking comparison.

It compares chunking strategies over the local budget corpus and deterministic
test queries without calling OpenAI. The fake keyword embedder is intentionally
simple: it teaches the retrieval shape without pretending to be production
semantic search.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.embedding_pipeline.comparison import (  # noqa: E402
    ChunkingComparisonService,
    ChunkingQueryComparisonService,
)
from app.embedding_pipeline.keyword_embedder import KeywordTextEmbedder  # noqa: E402
from app.embedding_pipeline.schemas import Budget  # noqa: E402


def load_budgets(path: Path) -> list[Budget]:
    """Load normalized budget fixtures from JSON."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [Budget.model_validate(item) for item in payload]


def load_queries(path: Path) -> list[dict[str, Any]]:
    """Load deterministic query fixtures from JSON."""
    payload = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(payload, list):
        raise ValueError("Query corpus must be a JSON list")

    return payload


def build_report(
    budgets: list[Budget],
    queries: list[dict[str, Any]],
    top_k: int,
) -> str:
    """Build a Markdown report for chunking stats and query rankings."""
    if top_k < 1:
        raise ValueError("top_k must be greater than or equal to 1")

    stats_comparison = ChunkingComparisonService().compare(budgets)
    query_service = ChunkingQueryComparisonService(text_embedder=KeywordTextEmbedder())

    lines = [
        "# Session 07 Chunking Comparison",
        "",
        "This report is deterministic and does not call OpenAI.",
        "It uses a small keyword-count fake embedder to show retrieval mechanics.",
        "",
        "## Strategy statistics",
        "",
        "| Strategy | Chunks | Total tokens | Avg tokens | Min tokens | Max tokens |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]

    for summary in stats_comparison.strategies:
        lines.append(
            "| "
            f"{summary.strategy_name} | "
            f"{summary.total_chunks} | "
            f"{summary.total_tokens} | "
            f"{summary.average_tokens:.2f} | "
            f"{summary.min_tokens} | "
            f"{summary.max_tokens} |"
        )

    lines.extend(["", "## Query rankings", ""])

    for query_item in queries:
        query_id = str(query_item["query_id"])
        query_text = str(query_item["query"])
        expected_budget_id = str(query_item["expected_budget_id"])
        expected_component_ids = ", ".join(query_item["expected_component_ids"])

        ranking = query_service.compare_query(
            budgets=budgets,
            query=query_text,
            top_k=top_k,
        )

        lines.extend(
            [
                f"### {query_id}",
                "",
                f"Query: {query_text}",
                "",
                f"Expected budget: {expected_budget_id}",
                "",
                f"Expected components: {expected_component_ids}",
                "",
            ]
        )

        for strategy in ranking.strategies:
            lines.extend(
                [
                    f"#### Strategy: {strategy.strategy_name}",
                    "",
                    "| Rank | Chunk ID | Score | Preview |",
                    "| ---: | --- | ---: | --- |",
                ]
            )

            for chunk in strategy.top_chunks:
                preview = chunk.text_preview.replace("|", "\\|")
                lines.append(
                    "| "
                    f"{chunk.rank} | "
                    f"{chunk.chunk_id} | "
                    f"{chunk.score:.4f} | "
                    f"{preview} |"
                )

            lines.append("")

    lines.extend(
        [
            "## Caveat",
            "",
            "This is a learning report, not a production retrieval evaluation.",
            "The fake embedder is deterministic and useful for mechanics, but it is not semantic.",
            "Live embedding and persisted retrieval should be evaluated separately.",
            "",
        ]
    )

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare Session 07 chunking strategies with deterministic queries."
    )
    parser.add_argument(
        "--budgets-path",
        type=Path,
        default=Path("data/budgets_sample.json"),
        help="Path to normalized budget sample JSON.",
    )
    parser.add_argument(
        "--queries-path",
        type=Path,
        default=Path("data/test_queries.json"),
        help="Path to deterministic test query JSON.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=2,
        help="Number of chunks to show per strategy and query.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional Markdown output path. Prints to stdout when omitted.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    budgets = load_budgets(args.budgets_path)
    queries = load_queries(args.queries_path)
    report = build_report(budgets=budgets, queries=queries, top_k=args.top_k)

    if args.output is None:
        print(report)
        return

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report + "\n", encoding="utf-8")
    print(f"Wrote chunking comparison report to {args.output}")


if __name__ == "__main__":
    main()
