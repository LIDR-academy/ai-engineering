from __future__ import annotations

import json
from pathlib import Path


def load_json(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_test_queries_file_exists_and_has_expected_shape() -> None:
    queries = load_json("data/test_queries.json")

    assert len(queries) >= 6

    query_ids = set()

    for item in queries:
        assert item["query_id"]
        assert item["query"]
        assert item["expected_budget_id"]
        assert item["expected_component_ids"]
        assert item["intent"]

        assert item["query_id"] not in query_ids
        query_ids.add(item["query_id"])

        assert isinstance(item["expected_component_ids"], list)
        assert all(component_id for component_id in item["expected_component_ids"])


def test_test_queries_reference_existing_sample_budgets_and_components() -> None:
    budgets = load_json("data/budgets_sample.json")
    queries = load_json("data/test_queries.json")

    budget_ids = {budget["budget_id"] for budget in budgets}
    component_ids_by_budget = {
        budget["budget_id"]: {
            component["component_id"] for component in budget["components"]
        }
        for budget in budgets
    }

    for item in queries:
        expected_budget_id = item["expected_budget_id"]

        assert expected_budget_id in budget_ids

        expected_component_ids = set(item["expected_component_ids"])
        existing_component_ids = component_ids_by_budget[expected_budget_id]

        assert expected_component_ids <= existing_component_ids


def test_test_queries_cover_all_sample_budgets() -> None:
    budgets = load_json("data/budgets_sample.json")
    queries = load_json("data/test_queries.json")

    budget_ids = {budget["budget_id"] for budget in budgets}
    covered_budget_ids = {item["expected_budget_id"] for item in queries}

    assert budget_ids <= covered_budget_ids
