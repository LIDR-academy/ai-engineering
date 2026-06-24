import json
from pathlib import Path


def test_capture_builds_search_payload_from_case() -> None:
    from evals.session08_search_quality.capture import build_search_payload
    from evals.session08_search_quality.evaluator import SearchQualityCase

    case = SearchQualityCase(
        case_id="auth",
        query=" REST API with JWT authentication ",
        expected_component_ids=("AUTH-001",),
        answerable=True,
    )

    assert build_search_payload(case, top_k=3) == {
        "query": "REST API with JWT authentication",
        "k": 3,
    }


def test_capture_responses_uses_case_ids_and_injected_http_client() -> None:
    from evals.session08_search_quality.capture import capture_responses
    from evals.session08_search_quality.evaluator import SearchQualityCase

    calls = []

    def fake_post_search(*, base_url, payload, timeout_seconds):
        calls.append(
            {
                "base_url": base_url,
                "payload": payload,
                "timeout_seconds": timeout_seconds,
            }
        )
        return {
            "query": payload["query"],
            "k": payload["k"],
            "results": [
                {
                    "distance": 0.12,
                    "metadata": {"component_id": "AUTH-001"},
                }
            ],
        }

    cases = [
        SearchQualityCase(
            case_id="auth",
            query="OAuth authentication",
            expected_component_ids=("AUTH-001",),
        )
    ]

    responses = capture_responses(
        cases=cases,
        base_url="http://example.test",
        top_k=5,
        timeout_seconds=9,
        post_search_fn=fake_post_search,
    )

    assert list(responses) == ["auth"]
    assert responses["auth"]["results"][0]["metadata"]["component_id"] == "AUTH-001"
    assert calls == [
        {
            "base_url": "http://example.test",
            "payload": {"query": "OAuth authentication", "k": 5},
            "timeout_seconds": 9,
        }
    ]


def test_validate_response_map_rejects_missing_case() -> None:
    import pytest

    from evals.session08_search_quality.capture import validate_response_map
    from evals.session08_search_quality.evaluator import SearchQualityCase

    cases = [
        SearchQualityCase(
            case_id="auth",
            query="OAuth authentication",
            expected_component_ids=("AUTH-001",),
        )
    ]

    with pytest.raises(ValueError, match="Missing captured response for case_id=auth"):
        validate_response_map(cases=cases, responses_by_case_id={})


def test_validate_response_map_rejects_bad_results_shape() -> None:
    import pytest

    from evals.session08_search_quality.capture import validate_response_map
    from evals.session08_search_quality.evaluator import SearchQualityCase

    cases = [
        SearchQualityCase(
            case_id="auth",
            query="OAuth authentication",
            expected_component_ids=("AUTH-001",),
        )
    ]

    with pytest.raises(ValueError, match="auth: results must be a list"):
        validate_response_map(
            cases=cases,
            responses_by_case_id={"auth": {"results": {"bad": "shape"}}},
        )


def test_write_json_atomically_writes_pretty_json_and_removes_tmp(tmp_path: Path) -> None:
    from evals.session08_search_quality.capture import write_json_atomically

    output = tmp_path / "responses.json"

    write_json_atomically(output, {"auth": {"results": []}})

    assert json.loads(output.read_text(encoding="utf-8")) == {"auth": {"results": []}}
    assert not Path(str(output) + ".tmp").exists()


def test_write_report_from_responses_scores_captured_payloads(tmp_path: Path) -> None:
    from evals.session08_search_quality.capture import write_report_from_responses
    from evals.session08_search_quality.evaluator import SearchQualityCase

    report = tmp_path / "REPORT.md"
    cases = [
        SearchQualityCase(
            case_id="auth",
            query="OAuth authentication",
            expected_component_ids=("AUTH-001",),
            answerable=True,
        )
    ]

    write_report_from_responses(
        cases=cases,
        responses_by_case_id={
            "auth": {
                "results": [
                    {
                        "distance": 0.1,
                        "metadata": {"component_id": "AUTH-001"},
                    }
                ]
            }
        },
        report_path=report,
    )

    text = report.read_text(encoding="utf-8")
    assert "Session 08 Search Quality Evaluation" in text
    assert "Answerable top-k hits: 1" in text
    assert "`auth`: pass" in text


def test_capture_cli_dry_run_prints_payloads_without_writing_files(
    tmp_path: Path,
    capsys,
) -> None:
    from evals.session08_search_quality.capture import main

    cases = tmp_path / "cases.jsonl"
    output = tmp_path / "responses.json"
    cases.write_text(
        '{"case_id":"auth","query":"OAuth authentication","expected_component_ids":["AUTH-001"],"answerable":true}\n',
        encoding="utf-8",
    )

    exit_code = main(
        [
            "--cases",
            str(cases),
            "--output",
            str(output),
            "--dry-run",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Dry run only" in captured.out
    assert "OAuth authentication" in captured.out
    assert not output.exists()
