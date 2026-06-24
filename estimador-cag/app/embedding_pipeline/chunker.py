"""
LAYER: embedding_pipeline chunker
RESPONSIBILITY: Convert normalized budget JSON into structural text chunks.
WHY IT EXISTS: Embedding a whole budget JSON creates one blurry vector. For this
               dataset, one budget component is the useful semantic unit, while
               parent context keeps short component names interpretable.
"""

import tiktoken

from app.embedding_pipeline.schemas import Budget, Chunk

EMBEDDING_MODEL = "text-embedding-3-small"


def _encoding_for_embedding_model():
    """Return the tokenizer used for the embedding model, with a safe fallback."""
    try:
        return tiktoken.encoding_for_model(EMBEDDING_MODEL)
    except KeyError:
        return tiktoken.get_encoding("cl100k_base")


class JSONStructuralChunker:
    """
    Structural chunker for normalized budget JSON.

    It deliberately does not implement overlap, fixed-size splitting, semantic
    chunking, hierarchical chunking, late chunking, or contextual retrieval.
    Those are future comparison strategies, not the Session 07 minimum pipeline.
    """

    def __init__(self) -> None:
        self._encoding = _encoding_for_embedding_model()

    def chunk(self, budgets: list[Budget]) -> list[Chunk]:
        """Create one chunk per budget component."""
        chunks: list[Chunk] = []

        for budget in budgets:
            for component in budget.components:
                text = self._build_chunk_text(budget=budget, component_id=component.component_id)
                chunks.append(
                    Chunk(
                        chunk_id=f"{budget.budget_id}::{component.component_id}",
                        text=text,
                        metadata={
                            "budget_id": budget.budget_id,
                            "component_id": component.component_id,
                            "client_name": budget.client_metadata.name,
                            "client_sector": budget.client_metadata.sector,
                            "client_country": budget.client_metadata.country,
                            "main_technology": budget.main_technology,
                            "year": budget.year,
                            "complexity": component.complexity,
                            "estimated_hours": component.estimated_hours,
                            "tech_stack": component.tech_stack,
                        },
                        token_count=len(self._encoding.encode(text)),
                    )
                )

        return chunks

    def _build_chunk_text(self, budget: Budget, component_id: str) -> str:
        component = next(
            candidate for candidate in budget.components if candidate.component_id == component_id
        )
        dependencies = ", ".join(component.dependencies) if component.dependencies else "none"

        return "\n".join(
            [
                f"[Project: {budget.project_summary}]",
                (
                    f"[Client sector: {budget.client_metadata.sector} | "
                    f"Country: {budget.client_metadata.country} | "
                    f"Year: {budget.year} | "
                    f"Main technology: {budget.main_technology} | "
                    f"Total estimated hours: {budget.total_estimated_hours}]"
                ),
                "",
                f"Component: {component.name}",
                f"Description: {component.description}",
                f"Tech stack: {', '.join(component.tech_stack)}",
                f"Complexity: {component.complexity}",
                f"Estimated hours: {component.estimated_hours}",
                f"Dependencies: {dependencies}",
            ]
        )
