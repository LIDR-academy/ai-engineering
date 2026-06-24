from pathlib import Path


def test_session08_search_quality_dataset_contains_canonical_queries() -> None:
    from evals.session08_search_quality.evaluator import DEFAULT_CASES_PATH, load_cases

    cases = load_cases(DEFAULT_CASES_PATH)

    assert [case.case_id for case in cases] == [
        "auth_jwt_finance",
        "auth_token_banking",
        "restaurant_negative_control",
        "external_integration",
        "kubernetes_migration",
    ]
    assert [case.query for case in cases] == [
        "REST API development with JWT authentication for financial sector",
        "secure backend service with token-based access control for banking applications",
        "mobile application for restaurant reservations",
        "integration with external system",
        "migration from monolith to microservices architecture using Kubernetes",
    ]


def test_session08_search_quality_eval_detects_expected_top_k_hit() -> None:
    from evals.session08_search_quality.evaluator import (
        SearchQualityCase,
        evaluate_response,
    )

    case = SearchQualityCase(
        case_id="auth_jwt_finance",
        query="REST API development with JWT authentication for financial sector",
        expected_component_ids=("AUTH-001",),
        answerable=True,
        notes="Authentication query should retrieve authentication component.",
    )

    evaluation = evaluate_response(
        case,
        {
            "results": [
                {
                    "distance": 0.42,
                    "metadata": {"component_id": "INT-001"},
                },
                {
                    "distance": 0.11,
                    "metadata": {"component_id": "AUTH-001"},
                },
            ]
        },
    )

    assert evaluation.top_k_hit is True
    assert evaluation.best_expected_rank == 2
    assert evaluation.nearest_component_id == "INT-001"
    assert evaluation.quality_label == "pass"


def test_session08_search_quality_eval_flags_negative_control_nearest_neighbor() -> None:
    from evals.session08_search_quality.evaluator import (
        SearchQualityCase,
        evaluate_response,
    )

    case = SearchQualityCase(
        case_id="restaurant_negative_control",
        query="mobile application for restaurant reservations",
        expected_component_ids=(),
        answerable=False,
        notes="Negative control should expose nearest-neighbor behavior.",
    )

    evaluation = evaluate_response(
        case,
        {
            "results": [
                {
                    "distance": 0.71,
                    "metadata": {"component_id": "UI-001"},
                }
            ]
        },
    )

    assert evaluation.top_k_hit is False
    assert evaluation.best_expected_rank is None
    assert evaluation.out_of_domain_returned_results is True
    assert evaluation.quality_label == "negative_control_nearest_neighbor"


def test_session08_search_quality_summary_counts_answerable_and_negative_cases() -> None:
    from evals.session08_search_quality.evaluator import (
        SearchQualityCase,
        evaluate_response,
        summarize_evaluations,
    )

    evaluations = [
        evaluate_response(
            SearchQualityCase(
                case_id="auth",
                query="auth",
                expected_component_ids=("AUTH-001",),
                answerable=True,
            ),
            {"results": [{"metadata": {"component_id": "AUTH-001"}, "distance": 0.1}]},
        ),
        evaluate_response(
            SearchQualityCase(
                case_id="migration",
                query="migration",
                expected_component_ids=("MIG-001",),
                answerable=True,
            ),
            {"results": [{"metadata": {"component_id": "AUTH-001"}, "distance": 0.5}]},
        ),
        evaluate_response(
            SearchQualityCase(
                case_id="negative",
                query="restaurant",
                expected_component_ids=(),
                answerable=False,
            ),
            {"results": [{"metadata": {"component_id": "UI-001"}, "distance": 0.8}]},
        ),
    ]

    summary = summarize_evaluations(evaluations)

    assert summary["case_count"] == 3
    assert summary["answerable_case_count"] == 2
    assert summary["answerable_top_k_hits"] == 1
    assert summary["answerable_top_k_hit_rate"] == 0.5
    assert summary["negative_control_count"] == 1
    assert summary["negative_controls_returning_results"] == 1


def test_session08_search_quality_report_is_honest_about_scope() -> None:
    from evals.session08_search_quality.evaluator import (
        SearchQualityCase,
        evaluate_response,
        render_markdown_report,
        summarize_evaluations,
    )

    evaluations = [
        evaluate_response(
            SearchQualityCase(
                case_id="auth",
                query="auth",
                expected_component_ids=("AUTH-001",),
                answerable=True,
            ),
            {"results": [{"metadata": {"component_id": "AUTH-001"}, "distance": 0.1}]},
        )
    ]

    report = render_markdown_report(
        summary=summarize_evaluations(evaluations),
        evaluations=evaluations,
    )

    assert "Session 08 Search Quality Evaluation" in report
    assert "No LLM judge" in report
    assert "No live provider call" in report
    assert "does not claim benchmark superiority" in report
    assert "beats" not in report.lower()


def test_session08_search_quality_report_file_documents_offline_scope() -> None:
    report = Path("evals/session08_search_quality/REPORT.md")

    assert report.exists()
    text = report.read_text(encoding="utf-8")

    assert "Session 08 Search Quality Evaluation" in text
    assert "offline evaluator" in text
    assert "No LLM judge" in text
    assert "No live provider call" in text
    assert "not a Task 09 implementation claim" in text
