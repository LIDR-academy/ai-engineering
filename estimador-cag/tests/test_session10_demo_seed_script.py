import json
import subprocess
import sys
from pathlib import Path

from scripts.seed_session10_demo_data import SOURCE_PREFIX, build_seed_plan


def test_session10_demo_seed_plan_matches_sample_budget_corpus() -> None:
    plan = build_seed_plan()

    assert len(plan) == 4
    assert sum(len(document.chunks) for document in plan) == 8
    assert {document.budget_id for document in plan} == {
        "BUD-2024-014",
        "BUD-2024-021",
        "BUD-2025-003",
        "BUD-2025-011",
    }
    assert all(document.source_path.startswith(SOURCE_PREFIX) for document in plan)

    all_chunks = [chunk for document in plan for chunk in document.chunks]
    auth_chunk = next(chunk for chunk in all_chunks if chunk.metadata["component_id"] == "AUTH-001")

    assert auth_chunk.metadata["budget_id"] == "BUD-2024-014"
    assert auth_chunk.metadata["client_sector"] == "finance"
    assert auth_chunk.metadata["client_country"] == "ES"
    assert auth_chunk.embedding
    assert "OAuth 2.0 authentication backend" in auth_chunk.content


def test_session10_demo_seed_script_dry_run_is_cli_safe() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/seed_session10_demo_data.py", "--dry-run"],
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(result.stdout)

    assert payload["mode"] == "dry_run"
    assert payload["documents_planned"] == 4
    assert payload["chunks_planned"] == 8
    assert "data/budgets_sample.json::BUD-2024-014" in payload["source_paths"]
    assert "DEEPSEEK_API_KEY" not in result.stdout
    assert "Bearer " not in result.stdout


def test_session10_demo_seed_script_documents_idempotent_source_lookup() -> None:
    source = Path("scripts/seed_session10_demo_data.py").read_text(encoding="utf-8")

    assert "find_document_id_by_source_path" in source
    assert "skipped_documents" in source
    assert "session10_demo" in source
    assert "DOCUMENT_TYPE" in source
