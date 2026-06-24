import json
from pathlib import Path

from evals.session10_retrieval.evaluator import load_golden_cases
from evals.session10_retrieval.run import (
    build_component_chunks,
    run_retrieval_measurement,
)


def test_build_component_chunks_from_budget_sample():
    chunks = build_component_chunks(Path("data/budgets_sample.json"))

    assert len(chunks) == 8

    auth_chunk = next(
        chunk for chunk in chunks if chunk.metadata["component_id"] == "AUTH-001"
    )

    assert auth_chunk.metadata["budget_id"] == "BUD-2024-014"
    assert auth_chunk.metadata["client_sector"] == "finance"
    assert auth_chunk.metadata["main_technology"] == "ruby_on_rails"
    assert "OAuth 2.0 authentication backend" in auth_chunk.content
    assert "JWT-based session management" in auth_chunk.content


def test_run_retrieval_measurement_writes_json_and_report(tmp_path):
    output_path = tmp_path / "results.json"
    report_path = tmp_path / "REPORT.md"

    payload = run_retrieval_measurement(
        golden_path=Path("evals/session10_retrieval/golden_retrieval.json"),
        budgets_path=Path("data/budgets_sample.json"),
        output_path=output_path,
        report_path=report_path,
        k=5,
        recall_k=8,
    )

    assert output_path.exists()
    assert report_path.exists()

    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert written == payload

    assert [summary["config_id"] for summary in payload["summaries"]] == [
        "A",
        "B",
        "C",
        "D",
    ]
    golden_cases = load_golden_cases(Path("evals/session10_retrieval/golden_retrieval.json"))
    assert len(payload["evaluations"]) == len(golden_cases) * 4
    assert all(summary["case_count"] == len(golden_cases) for summary in payload["summaries"])

    for summary in payload["summaries"]:
        assert summary["case_count"] == len(golden_cases)
        assert 0 <= summary["mean_precision_at_5"] <= 1
        assert 0 <= summary["budget_hit_rate_at_5"] <= 1
        assert 0 <= summary["component_hit_rate_at_5"] <= 1
        assert summary["median_latency_ms"] >= 0

    report = report_path.read_text(encoding="utf-8")
    assert "# Session 10 Retrieval A/B/C/D Evaluation" in report
    assert "| A | Vector | No |" in report
    assert "| D | Hybrid | Yes |" in report


def test_runner_keeps_case_details_for_audit(tmp_path):
    payload = run_retrieval_measurement(
        golden_path=Path("evals/session10_retrieval/golden_retrieval.json"),
        budgets_path=Path("data/budgets_sample.json"),
        output_path=tmp_path / "results.json",
        report_path=tmp_path / "REPORT.md",
        k=5,
        recall_k=8,
    )

    first = payload["evaluations"][0]

    assert {
        "config_id",
        "query_id",
        "query",
        "relevant_budget_ids",
        "expected_component_ids",
        "top_budget_ids",
        "top_component_ids",
        "precision_at_k",
        "budget_hit_at_k",
        "component_hit_at_k",
        "latency_ms",
    } <= set(first)



def test_hashing_vectorizer_is_stable_across_python_hash_seeds():
    import os
    import subprocess
    import sys

    script = (
        "import json;"
        "from evals.session10_retrieval.run import HashingVectorizer;"
        "vector = HashingVectorizer().embed('OAuth banking authentication');"
        "print(json.dumps([index for index, value in enumerate(vector) if value]))"
    )

    env_one = os.environ.copy()
    env_one["PYTHONHASHSEED"] = "1"
    env_two = os.environ.copy()
    env_two["PYTHONHASHSEED"] = "2"

    first = subprocess.check_output(
        [sys.executable, "-c", script],
        cwd=Path.cwd(),
        env=env_one,
        text=True,
    ).strip()
    second = subprocess.check_output(
        [sys.executable, "-c", script],
        cwd=Path.cwd(),
        env=env_two,
        text=True,
    ).strip()

    assert first == second



def test_committed_report_describes_challenge_queries():
    report = Path("evals/session10_retrieval/REPORT.md").read_text(encoding="utf-8")

    assert "challenge queries" in report
    assert "ambiguous and low-signal" in report
    assert "small course corpus" in report
