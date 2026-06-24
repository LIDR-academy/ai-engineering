import json
from pathlib import Path

from evals.session10_retrieval.evaluator import (
    RETRIEVAL_CONFIGS,
    evaluate_case,
    load_golden_cases,
    render_markdown_report,
    summarize_variant_results,
)


def test_golden_cases_use_real_budget_level_annotations():
    cases = load_golden_cases(Path("evals/session10_retrieval/golden_retrieval.json"))

    assert len(cases) >= 5
    assert {case.query_id for case in cases} >= {
        "Q-AUTH-001",
        "Q-AUDIT-001",
        "Q-CHECKOUT-001",
        "Q-INVENTORY-001",
        "Q-DOCS-001",
        "Q-TELEMETRY-001",
        "Q-ALERTS-001",
    }
    assert all(case.relevant_budget_ids for case in cases)
    assert all(case.expected_component_ids for case in cases)

    known_budget_ids = {
        budget["budget_id"]
        for budget in json.loads(Path("data/budgets_sample.json").read_text(encoding="utf-8"))
    }
    annotated_budget_ids = {
        budget_id
        for case in cases
        for budget_id in case.relevant_budget_ids
    }

    assert annotated_budget_ids <= known_budget_ids


def test_retrieval_configs_cover_a_b_c_d():
    assert [config.config_id for config in RETRIEVAL_CONFIGS] == ["A", "B", "C", "D"]

    assert RETRIEVAL_CONFIGS[0].search_mode == "vector"
    assert RETRIEVAL_CONFIGS[0].use_reranker is False

    assert RETRIEVAL_CONFIGS[1].search_mode == "hybrid"
    assert RETRIEVAL_CONFIGS[1].use_reranker is False

    assert RETRIEVAL_CONFIGS[2].search_mode == "vector"
    assert RETRIEVAL_CONFIGS[2].use_reranker is True

    assert RETRIEVAL_CONFIGS[3].search_mode == "hybrid"
    assert RETRIEVAL_CONFIGS[3].use_reranker is True


def test_evaluate_case_uses_budget_precision_and_component_hit():
    case = load_golden_cases(Path("evals/session10_retrieval/golden_retrieval.json"))[0]

    result = evaluate_case(
        case=case,
        config_id="A",
        results=[
            {
                "metadata": {
                    "budget_id": "BUD-2024-014",
                    "component_id": "AUTH-001",
                }
            },
            {
                "metadata": {
                    "budget_id": "BUD-2024-021",
                    "component_id": "CHECKOUT-001",
                }
            },
        ],
        latency_ms=12,
        k=5,
    )

    assert result.config_id == "A"
    assert result.query_id == case.query_id
    assert result.relevant_budget_ids == case.relevant_budget_ids
    assert result.top_budget_ids[:2] == ("BUD-2024-014", "BUD-2024-021")
    assert result.precision_at_k == 0.2
    assert result.budget_hit_at_k is True
    assert result.best_budget_rank == 1
    assert result.component_hit_at_k is True
    assert result.best_component_rank == 1
    assert result.latency_ms == 12


def test_summarize_variant_results_uses_mean_precision_and_median_latency():
    case = load_golden_cases(Path("evals/session10_retrieval/golden_retrieval.json"))[0]

    evaluations = [
        evaluate_case(
            case=case,
            config_id="A",
            results=[
                {"metadata": {"budget_id": "BUD-2024-014", "component_id": "AUTH-001"}},
            ],
            latency_ms=30,
            k=5,
        ),
        evaluate_case(
            case=case,
            config_id="A",
            results=[
                {"metadata": {"budget_id": "BUD-2024-021", "component_id": "CHECKOUT-001"}},
            ],
            latency_ms=10,
            k=5,
        ),
        evaluate_case(
            case=case,
            config_id="A",
            results=[
                {"metadata": {"budget_id": "BUD-2024-014", "component_id": "AUTH-001"}},
            ],
            latency_ms=20,
            k=5,
        ),
    ]

    summary = summarize_variant_results(config_id="A", evaluations=evaluations)

    assert summary["config_id"] == "A"
    assert summary["case_count"] == 3
    assert summary["mean_precision_at_5"] == 0.1333
    assert summary["budget_hit_rate_at_5"] == 0.6667
    assert summary["component_hit_rate_at_5"] == 0.6667
    assert summary["median_latency_ms"] == 20


def test_render_markdown_report_contains_comparison_table():
    case = load_golden_cases(Path("evals/session10_retrieval/golden_retrieval.json"))[0]
    evaluations = [
        evaluate_case(
            case=case,
            config_id="A",
            results=[
                {"metadata": {"budget_id": "BUD-2024-014", "component_id": "AUTH-001"}},
            ],
            latency_ms=20,
            k=5,
        )
    ]
    summaries = [summarize_variant_results(config_id="A", evaluations=evaluations)]

    report = render_markdown_report(
        summaries=summaries,
        evaluations=evaluations,
        k=5,
    )

    assert "# Session 10 Retrieval A/B/C/D Evaluation" in report
    assert "| Config | Search | Reranking | result-budget precision@5 | unique-budget precision@5 | budget hit@5 | component hit@5 | top1 budget | top1 component | median latency ms |" in report
    assert "| A | Vector | No | 0.2000 | 0.2000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 20 |" in report
    assert "Limitations" in report



def test_evaluate_case_reports_unique_budget_precision_and_top1_accuracy():
    case = load_golden_cases(Path("evals/session10_retrieval/golden_retrieval.json"))[0]

    result = evaluate_case(
        case=case,
        config_id="A",
        results=[
            {
                "metadata": {
                    "budget_id": "BUD-2024-014",
                    "component_id": "AUDIT-001",
                }
            },
            {
                "metadata": {
                    "budget_id": "BUD-2024-014",
                    "component_id": "AUTH-001",
                }
            },
            {
                "metadata": {
                    "budget_id": "BUD-2024-021",
                    "component_id": "CHECKOUT-001",
                }
            },
        ],
        latency_ms=9,
        k=5,
    )

    assert result.result_budget_precision_at_k == 0.4
    assert result.precision_at_k == result.result_budget_precision_at_k
    assert result.unique_budget_precision_at_k == 0.2
    assert result.top1_budget_accuracy is True
    assert result.top1_component_accuracy is False
    assert result.best_budget_rank == 1
    assert result.best_component_rank == 2


def test_summary_includes_unique_precision_and_top1_rates():
    case = load_golden_cases(Path("evals/session10_retrieval/golden_retrieval.json"))[0]

    evaluations = [
        evaluate_case(
            case=case,
            config_id="A",
            results=[
                {"metadata": {"budget_id": "BUD-2024-014", "component_id": "AUTH-001"}},
                {"metadata": {"budget_id": "BUD-2024-014", "component_id": "AUDIT-001"}},
            ],
            latency_ms=1,
            k=5,
        ),
        evaluate_case(
            case=case,
            config_id="A",
            results=[
                {"metadata": {"budget_id": "BUD-2024-014", "component_id": "AUDIT-001"}},
                {"metadata": {"budget_id": "BUD-2024-014", "component_id": "AUTH-001"}},
            ],
            latency_ms=3,
            k=5,
        ),
    ]

    summary = summarize_variant_results(config_id="A", evaluations=evaluations)

    assert summary["mean_result_budget_precision_at_5"] == 0.4
    assert summary["mean_unique_budget_precision_at_5"] == 0.2
    assert summary["top1_budget_accuracy"] == 1.0
    assert summary["top1_component_accuracy"] == 0.5



def test_golden_cases_include_harder_ambiguous_queries():
    cases = load_golden_cases(Path("evals/session10_retrieval/golden_retrieval.json"))
    case_ids = {case.query_id for case in cases}

    assert len(cases) >= 12
    assert {
        "Q-AUTH-AUDIT-AMBIGUOUS",
        "Q-CHECKOUT-INVENTORY-AMBIGUOUS",
        "Q-INTAKE-DOCS-AMBIGUOUS",
        "Q-TELEMETRY-ALERTS-AMBIGUOUS",
        "Q-LOW-SIGNAL-BACKEND-REFERENCE",
    } <= case_ids

    challenge_cases = [
        case
        for case in cases
        if case.query_id
        in {
            "Q-AUTH-AUDIT-AMBIGUOUS",
            "Q-CHECKOUT-INVENTORY-AMBIGUOUS",
            "Q-INTAKE-DOCS-AMBIGUOUS",
            "Q-TELEMETRY-ALERTS-AMBIGUOUS",
            "Q-LOW-SIGNAL-BACKEND-REFERENCE",
        }
    ]

    assert all(len(case.expected_component_ids) >= 1 for case in challenge_cases)
    assert any(len(case.expected_component_ids) > 1 for case in challenge_cases)
