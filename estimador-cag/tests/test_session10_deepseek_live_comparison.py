import json

import pytest

from evals.session10_retrieval.deepseek_live_comparison import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    DeepSeekLiveComparisonError,
    build_retrieval_messages,
    run_comparison,
    select_cases,
)


def test_deepseek_dry_run_writes_prompts_without_network(tmp_path, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_BASE_URL", raising=False)
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)

    output_path = tmp_path / "deepseek_dry_run.json"
    payload = run_comparison(output_path=output_path, max_cases=1, live=False)

    assert output_path.exists()
    assert payload["mode"] == "dry_run"
    assert payload["provider"] == "deepseek"
    assert payload["model"] == DEFAULT_MODEL
    assert payload["base_url"] == DEFAULT_BASE_URL
    assert payload["case_count"] == 1
    assert "baseline_prompt" in payload["records"][0]
    assert "retrieval_grounded_prompt" in payload["records"][0]

    serialized = output_path.read_text(encoding="utf-8")
    assert "DEEPSEEK_API_KEY" not in serialized
    assert "Bearer " not in serialized


def test_deepseek_live_mode_requires_api_key(tmp_path, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_BASE_URL", raising=False)
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)

    with pytest.raises(DeepSeekLiveComparisonError, match="DEEPSEEK_API_KEY"):
        run_comparison(output_path=tmp_path / "live.json", max_cases=1, live=True)


def test_retrieval_grounded_prompt_contains_evidence_contract():
    case = select_cases(max_cases=1)[0]
    contexts = [
        {
            "rank": 1,
            "budget_id": "BUD-2024-014",
            "component_id": "AUTH-001",
            "content": "OAuth authentication backend with JWT session management.",
        }
    ]

    messages = build_retrieval_messages(case, contexts)
    joined = json.dumps(messages, ensure_ascii=False)

    assert "Use only the retrieved context" in joined
    assert "selected_budget_ids" in joined
    assert "selected_component_ids" in joined
    assert "BUD-2024-014" in joined
    assert "AUTH-001" in joined
