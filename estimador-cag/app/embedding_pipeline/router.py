"""
LAYER: embedding_pipeline router
RESPONSIBILITY: Expose structural chunking comparison and persistent embedding ingestion.
WHY IT EXISTS: Session 08 persists embedded chunks in PostgreSQL plus pgvector while
               keeping comparison endpoints deterministic for learning.
"""

from __future__ import annotations

import time
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import Field, TypeAdapter, ValidationError

from app.embedding_pipeline.chunker import JSONStructuralChunker
from app.embedding_pipeline.comparison import ChunkingQueryComparisonService, QueryRankingComparison
from app.embedding_pipeline.embedder import EMBEDDING_MODEL, OpenAIEmbedder
from app.embedding_pipeline.ingestion_service import (
    DocumentAlreadyIngestedError,
    IngestDocumentCommand,
    PersistentEmbeddingIngestionService,
)
from app.embedding_pipeline.keyword_embedder import KeywordTextEmbedder
from app.embedding_pipeline.schemas import (
    Budget,
    IngestRequest,
    PersistentIngestRequest,
    PersistentIngestResponse,
)
from app.persistence.database import AsyncSessionLocal
from app.persistence.repository import DocumentRepository

router = APIRouter()
logger = structlog.get_logger(__name__)


def get_query_comparison_service() -> ChunkingQueryComparisonService:
    """Build the deterministic comparison service for the lab endpoint."""
    return ChunkingQueryComparisonService(text_embedder=KeywordTextEmbedder())


def get_persistent_ingestion_service(session) -> PersistentEmbeddingIngestionService:
    """Build the Session 08 persistent ingestion service lazily.

    The caller owns the session and transaction boundary so a successful ingest
    commits atomically and provider/database failures roll back.
    """
    return PersistentEmbeddingIngestionService(
        chunker=JSONStructuralChunker(),
        embedder=OpenAIEmbedder(),
        repository=DocumentRepository(session),
    )


QueryComparisonServiceDependency = Annotated[
    ChunkingQueryComparisonService,
    Depends(get_query_comparison_service),
]


class CompareRequest(IngestRequest):
    """Request body for deterministic chunking comparison."""

    query: str = Field(min_length=1)
    top_k: Annotated[int, Field(ge=1)] = 3


@router.post("/ingest", response_model=PersistentIngestResponse)
async def ingest_embeddings(
    request: PersistentIngestRequest,
) -> PersistentIngestResponse | JSONResponse:
    """Persist a normalized historical budget document and its embedded chunks."""
    started = time.perf_counter()

    budgets_payload = request.content.get("budgets")
    if not isinstance(budgets_payload, list) or not budgets_payload:
        raise HTTPException(status_code=422, detail="content.budgets must be a non-empty list")

    try:
        budgets = TypeAdapter(list[Budget]).validate_python(budgets_payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from None

    try:
        async with AsyncSessionLocal.begin() as session:
            service = get_persistent_ingestion_service(session)
            result = await service.ingest_document(
                IngestDocumentCommand(
                    source_path=request.source_path,
                    document_type=request.document_type,
                    budgets=budgets,
                    metadata={"content_keys": sorted(request.content.keys())},
                )
            )
    except DocumentAlreadyIngestedError as exc:
        return JSONResponse(
            status_code=409,
            content={
                "detail": "Document already ingested",
                "document_id": exc.document_id,
            },
        )
    except Exception:
        logger.exception(
            "persistent_embedding_ingest_failed",
            source_path=request.source_path,
            document_type=request.document_type,
            model=EMBEDDING_MODEL,
        )
        raise HTTPException(status_code=500, detail="Embedding ingestion failed") from None

    return PersistentIngestResponse(
        document_id=result.document_id,
        chunks_created=result.chunks_created,
        embedding_dimension=result.embedding_dimension,
        ingestion_time_ms=int((time.perf_counter() - started) * 1000),
    )


@router.post("/compare", response_model=QueryRankingComparison)
def compare_embeddings(
    request: CompareRequest,
    comparison_service: QueryComparisonServiceDependency,
) -> QueryRankingComparison:
    """
    Compare chunking strategies for one query.

    This endpoint is a deterministic learning lab. It ranks chunks with a small
    keyword-count fake embedder, not with live OpenAI embeddings.
    """
    return comparison_service.compare_query(
        budgets=request.budgets,
        query=request.query,
        top_k=request.top_k,
    )
