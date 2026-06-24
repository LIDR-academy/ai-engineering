import json
from pathlib import Path

from app.embedding_pipeline.chunker import JSONStructuralChunker
from app.embedding_pipeline.schemas import Budget


def test_budgets_sample_json_matches_embedding_schema() -> None:
    path = Path("data/budgets_sample.json")
    payload = json.loads(path.read_text(encoding="utf-8"))

    budgets = [Budget.model_validate(item) for item in payload]

    assert len(budgets) >= 3
    assert all(len(budget.components) >= 2 for budget in budgets)


def test_budgets_sample_json_can_be_structurally_chunked() -> None:
    payload = json.loads(Path("data/budgets_sample.json").read_text(encoding="utf-8"))
    budgets = [Budget.model_validate(item) for item in payload]

    chunks = JSONStructuralChunker().chunk(budgets)

    assert len(chunks) == sum(len(budget.components) for budget in budgets)
    assert all("Project:" in chunk.text for chunk in chunks)
    assert all(chunk.token_count > 0 for chunk in chunks)
