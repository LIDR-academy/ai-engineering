"""
LAYER: embedding_pipeline schemas
RESPONSIBILITY: Define the typed contracts for budget chunking and embedding ingestion.
WHY IT EXISTS: Session 07 starts the RAG foundation by turning normalized budget JSON
               into validated chunks before any vector database or retrieval exists.
"""

from typing import TypeAlias

from pydantic import BaseModel, Field

MetadataValue: TypeAlias = str | int | float | bool | list[str]


class ClientMetadata(BaseModel):
    """Client context inherited by every component chunk."""

    name: str = Field(min_length=1)
    sector: str = Field(min_length=1)
    country: str = Field(min_length=1)


class BudgetComponent(BaseModel):
    """One estimable component inside a historical budget."""

    component_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    tech_stack: list[str] = Field(min_length=1)
    estimated_hours: int = Field(gt=0)
    complexity: str = Field(min_length=1)
    dependencies: list[str] = Field(default_factory=list)


class Budget(BaseModel):
    """A normalized historical budget produced by the previous CAG sessions."""

    budget_id: str = Field(min_length=1)
    client_metadata: ClientMetadata
    project_summary: str = Field(min_length=1)
    main_technology: str = Field(min_length=1)
    year: int = Field(ge=2000, le=2100)
    total_estimated_hours: int = Field(gt=0)
    components: list[BudgetComponent] = Field(min_length=1)


class Chunk(BaseModel):
    """A structural chunk ready to be embedded later."""

    chunk_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    metadata: dict[str, MetadataValue]
    token_count: int = Field(gt=0)


class EmbeddedChunk(Chunk):
    """A chunk plus its embedding vector."""

    embedding: list[float]


class IngestRequest(BaseModel):
    """Request body for the future POST /embeddings/ingest endpoint."""

    budgets: list[Budget] = Field(min_length=1)


class IngestStats(BaseModel):
    """Aggregate statistics returned by the future embedding ingestion endpoint."""

    total_budgets: int = Field(ge=0)
    total_chunks: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)
    model: str = Field(min_length=1)


class IngestResponse(BaseModel):
    """Response body for the future POST /embeddings/ingest endpoint."""

    chunks: list[EmbeddedChunk]
    stats: IngestStats


class PersistentIngestRequest(BaseModel):
    """Session 08 request body for persisted embedding ingestion."""

    source_path: str = Field(min_length=1)
    document_type: str = Field(min_length=1, max_length=50)
    content: dict[str, object]


class PersistentIngestResponse(BaseModel):
    """Session 08 response body for persisted embedding ingestion."""

    document_id: int = Field(ge=1)
    chunks_created: int = Field(ge=0)
    embedding_dimension: int = Field(ge=1)
    ingestion_time_ms: int = Field(ge=0)
