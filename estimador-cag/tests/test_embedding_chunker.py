from app.embedding_pipeline.chunker import JSONStructuralChunker
from app.embedding_pipeline.schemas import Budget


def sample_budget() -> Budget:
    return Budget.model_validate(
        {
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
                },
                {
                    "component_id": "AUDIT-001",
                    "name": "Audit logging",
                    "description": "Immutable audit trail for regulated account operations.",
                    "tech_stack": ["ruby_on_rails", "postgresql"],
                    "estimated_hours": 80,
                    "complexity": "medium",
                    "dependencies": ["AUTH-001"],
                },
            ],
        }
    )


def test_one_budget_component_becomes_one_chunk() -> None:
    chunks = JSONStructuralChunker().chunk([sample_budget()])

    assert len(chunks) == 2
    assert chunks[0].chunk_id == "BUD-2024-014::AUTH-001"
    assert chunks[1].chunk_id == "BUD-2024-014::AUDIT-001"


def test_chunk_text_includes_parent_context_and_component_details() -> None:
    chunk = JSONStructuralChunker().chunk([sample_budget()])[0]

    assert "Mobile banking API" in chunk.text
    assert "Client sector: finance" in chunk.text
    assert "Country: ES" in chunk.text
    assert "Year: 2024" in chunk.text
    assert "Main technology: ruby_on_rails" in chunk.text
    assert "Total estimated hours: 480" in chunk.text
    assert "OAuth 2.0 authentication backend" in chunk.text
    assert "JWT-based session management" in chunk.text
    assert "ruby_on_rails, postgresql, redis" in chunk.text


def test_chunk_metadata_contains_filterable_fields() -> None:
    chunk = JSONStructuralChunker().chunk([sample_budget()])[0]

    assert chunk.metadata == {
        "budget_id": "BUD-2024-014",
        "component_id": "AUTH-001",
        "client_name": "FintechCorp",
        "client_sector": "finance",
        "client_country": "ES",
        "main_technology": "ruby_on_rails",
        "year": 2024,
        "complexity": "high",
        "estimated_hours": 120,
        "tech_stack": ["ruby_on_rails", "postgresql", "redis"],
    }


def test_chunk_token_count_is_positive() -> None:
    chunk = JSONStructuralChunker().chunk([sample_budget()])[0]

    assert chunk.token_count > 0
