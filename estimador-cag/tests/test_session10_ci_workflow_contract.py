from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _workflow_text() -> str:
    return CI_WORKFLOW.read_text(encoding="utf-8")


def test_ci_push_filter_matches_gg_branches_with_slashes() -> None:
    text = _workflow_text()

    assert '"gg-**"' in text
    assert '"gg-*"' not in text


def test_ci_keeps_deterministic_dummy_provider_keys() -> None:
    text = _workflow_text()

    assert "OPENAI_API_KEY: test" in text
    assert "DEEPSEEK_API_KEY: test" in text
    assert "KIMI_API_KEY: test" in text


def test_ci_runs_lint_compile_and_pytest() -> None:
    text = _workflow_text()

    assert "uv run ruff check" in text
    assert "uv run python -m py_compile" in text
    assert "uv run pytest -q" in text
