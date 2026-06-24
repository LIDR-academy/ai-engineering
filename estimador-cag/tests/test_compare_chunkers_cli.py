from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts import compare_chunkers


def test_keyword_text_embedder_returns_one_vector_per_text() -> None:
    embedder = compare_chunkers.KeywordTextEmbedder()

    vectors = embedder.embed_texts(
        [
            "OAuth JWT authentication",
            "inventory synchronization",
        ]
    )

    assert len(vectors) == 2
    assert len(vectors[0]) == len(embedder.keywords)
    assert vectors[0] != vectors[1]


def test_build_report_includes_strategy_stats_and_query_rankings() -> None:
    project_root = Path(__file__).resolve().parents[1]

    budgets = compare_chunkers.load_budgets(project_root / "data/budgets_sample.json")
    queries = compare_chunkers.load_queries(project_root / "data/test_queries.json")

    report = compare_chunkers.build_report(
        budgets=budgets,
        queries=queries[:1],
        top_k=2,
    )

    assert "# Session 07 Chunking Comparison" in report
    assert "## Strategy statistics" in report
    assert "structural_component" in report
    assert "whole_budget" in report
    assert "## Query rankings" in report
    assert "Q-AUTH-001" in report
    assert "Expected budget: BUD-2024-014" in report
    assert "Expected components: AUTH-001" in report
    assert "BUD-2024-014::AUTH-001" in report
    assert "BUD-2024-014::whole_budget" in report


def test_compare_chunkers_script_help_runs_from_file_path() -> None:
    project_root = Path(__file__).resolve().parents[1]

    result = subprocess.run(
        [sys.executable, "scripts/compare_chunkers.py", "--help"],
        cwd=project_root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "--budgets-path" in result.stdout
    assert "--queries-path" in result.stdout
    assert "--top-k" in result.stdout


def test_compare_chunkers_script_runs_without_live_openai() -> None:
    project_root = Path(__file__).resolve().parents[1]

    result = subprocess.run(
        [
            sys.executable,
            "scripts/compare_chunkers.py",
            "--top-k",
            "1",
        ],
        cwd=project_root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "# Session 07 Chunking Comparison" in result.stdout
    assert "Q-AUTH-001" in result.stdout
    assert "structural_component" in result.stdout
    assert "whole_budget" in result.stdout
