import pytest
from pydantic import ValidationError

from app.embedding_pipeline.schemas import Budget, IngestRequest


def sample_budget_payload() -> dict:
    return {
        "budget_id": "BUD-2024-014",
        "client_metadata": {
            "name": "FintechCorp",
            "sector": "finance",
            "country": "ES",
        },
        "project_summary": "Mobile banking API with OAuth 2.0 authentication and PSD2 compliance",
        "main_technology": "ruby_on_rails",
        "year": 2024,
        "total_estimated_hours": 480,
        "components": [
            {
                "component_id": "AUTH-001",
                "name": "OAuth 2.0 authentication backend",
                "description": (
                    "Implementation of OAuth 2.0 flows with JWT-based session management, "
                    "multi-tenant token isolation, and rate limiting per client."
                ),
                "tech_stack": ["ruby_on_rails", "postgresql", "redis"],
                "estimated_hours": 120,
                "complexity": "high",
                "dependencies": [],
            }
        ],
    }


def test_budget_payload_parses_correctly() -> None:
    budget = Budget.model_validate(sample_budget_payload())

    assert budget.budget_id == "BUD-2024-014"
    assert budget.client_metadata.sector == "finance"
    assert budget.components[0].component_id == "AUTH-001"
    assert budget.components[0].tech_stack == ["ruby_on_rails", "postgresql", "redis"]


def test_ingest_request_requires_at_least_one_budget() -> None:
    with pytest.raises(ValidationError):
        IngestRequest.model_validate({"budgets": []})


def test_budget_component_rejects_empty_tech_stack() -> None:
    payload = sample_budget_payload()
    payload["components"][0]["tech_stack"] = []

    with pytest.raises(ValidationError):
        Budget.model_validate(payload)
