from pathlib import Path

BRIDGE = Path("evals/session08_search_quality/TASK09_READINESS.md")


def test_task09_readiness_bridge_file_exists() -> None:
    assert BRIDGE.exists()


def test_task09_readiness_bridge_declares_scope_and_source_status() -> None:
    text = BRIDGE.read_text(encoding="utf-8")

    assert "# Session 08 to Task 09 Readiness Bridge" in text
    assert "official Task 09 statement is still the stronger source of truth" in text
    assert "not a Task 09 implementation" in text
    assert "not a benchmark superiority claim" in text
    assert "not production readiness evidence" in text


def test_task09_readiness_bridge_lists_reusable_session08_artifacts() -> None:
    text = BRIDGE.read_text(encoding="utf-8")

    assert "evals/session08_search_quality/cases.jsonl" in text
    assert "evals/session08_search_quality/evaluator.py" in text
    assert "evals/session08_search_quality/capture.py" in text
    assert "evals/session08_search_quality/REPORT.md" in text
    assert "README search-quality workflow" in text


def test_task09_readiness_bridge_maps_to_likely_task09_deliverables() -> None:
    text = BRIDGE.read_text(encoding="utf-8")

    assert "| Likely Task 09 deliverable | Session 08 bridge status | Next Task 09 action |" in text
    assert "Evaluation dataset or test set" in text
    assert "Repeatable evaluation runner or script" in text
    assert "Metrics for answer quality or retrieval quality" in text
    assert "Hallucination or unsupported-claim detection" in text
    assert "Grounding or evidence-coverage checks" in text
    assert "README documentation" in text


def test_task09_readiness_bridge_lists_missing_task09_work() -> None:
    text = BRIDGE.read_text(encoding="utf-8")

    assert "Generated answer evaluation" in text
    assert "Grounding checks over answer claims" in text
    assert "Unsupported-claim detection" in text
    assert "Task 09 evaluation report" in text
    assert "Official Task 09 statement ingestion" in text


def test_task09_readiness_bridge_recommends_next_branch_and_first_slice() -> None:
    text = BRIDGE.read_text(encoding="utf-8")

    assert "gg-session-09-evaluation-quality" in text
    assert "Slice 1: official Task 09 audit and dataset schema" in text
    assert "No LLM calls" in text
    assert "No live provider dependency" in text
    assert "No benchmark claims" in text


def test_task09_readiness_bridge_has_decision_json() -> None:
    text = BRIDGE.read_text(encoding="utf-8")

    assert '"decision": "accept_bridge"' in text
    assert '"next_action": "start_task09_on_dedicated_branch_after_official_task_statement_audit"' in text
