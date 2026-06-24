"""
LAYER: persistence repository
RESPONSIBILITY: Persist and retrieve pgvector-backed document/chunk records.
WHY IT EXISTS: Keeps SQLAlchemy details out of FastAPI routers and ingestion
               orchestration while preserving transaction control in services.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.models import Chunk, Document

EMBEDDING_DIMENSION = 1536


@dataclass(frozen=True)
class ChunkInsert:
    """A chunk row ready to be inserted into pgvector storage."""

    chunk_type: str
    content: str
    embedding: list[float] | None
    metadata: dict[str, Any]

    def __post_init__(self) -> None:
        if self.embedding is not None and len(self.embedding) != EMBEDDING_DIMENSION:
            raise ValueError(f"Embedding dimension must be {EMBEDDING_DIMENSION}")


@dataclass(frozen=True)
class ChunkLexicalSearchResult:
    """One chunk returned by PostgreSQL full text search."""

    chunk_id: int
    document_id: int
    chunk_type: str
    content: str
    rank: float
    metadata: dict[str, Any]


@dataclass(frozen=True)
class ChunkSearchResult:
    """A persisted chunk returned by semantic search."""

    chunk_id: int
    document_id: int
    chunk_type: str
    content: str
    distance: float
    metadata: dict[str, Any]


def _normalize_metadata_filters(
    metadata_filters: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return non-empty JSONB containment filters."""
    if not metadata_filters:
        return {}

    normalized: dict[str, Any] = {}
    for key, value in metadata_filters.items():
        if value is None:
            continue

        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                normalized[key] = stripped
            continue

        if isinstance(value, list):
            cleaned = [
                item.strip() if isinstance(item, str) else item
                for item in value
                if item is not None and (not isinstance(item, str) or item.strip())
            ]
            if cleaned:
                normalized[key] = cleaned
            continue

        normalized[key] = value

    return normalized


class DocumentRepository:
    """Repository for document and chunk persistence.

    This class deliberately does not commit. Callers own the transaction boundary,
    which allows ingestion to rollback document and chunk writes atomically.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def find_document_id_by_source_path(self, source_path: str) -> int | None:
        """Return an existing document id for a source path, if present."""
        result = await self.session.execute(
            select(Document.id).where(Document.source_path == source_path)
        )
        return result.scalar_one_or_none()

    async def add_document_with_chunks(
        self,
        *,
        source_path: str,
        document_type: str,
        chunks: list[ChunkInsert],
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """Add one document and its chunks to the current session."""
        if not chunks:
            raise ValueError("At least one chunk is required")

        document = Document(
            source_path=source_path,
            document_type=document_type,
            document_metadata=metadata or {},
        )
        self.session.add(document)
        await self.session.flush()

        document_id = int(document.id)
        for chunk in chunks:
            self.session.add(
                Chunk(
                    document_id=document_id,
                    chunk_type=chunk.chunk_type,
                    content=chunk.content,
                    embedding=chunk.embedding,
                    chunk_metadata=chunk.metadata,
                )
            )

        await self.session.flush()
        return document_id

    async def search_chunks_by_embedding(
        self,
        *,
        query_embedding: list[float],
        k: int,
        metadata_filters: Mapping[str, Any] | None = None,
    ) -> list[ChunkSearchResult]:
        """Return top-k persisted chunks ordered by cosine distance."""
        if k <= 0:
            raise ValueError("k must be positive")
        if len(query_embedding) != EMBEDDING_DIMENSION:
            raise ValueError(f"Embedding dimension must be {EMBEDDING_DIMENSION}")

        normalized_filters = _normalize_metadata_filters(metadata_filters)

        distance = Chunk.embedding.cosine_distance(query_embedding)
        statement = (
            select(
                Chunk.id.label("chunk_id"),
                Chunk.document_id.label("document_id"),
                Chunk.chunk_type.label("chunk_type"),
                Chunk.content.label("content"),
                distance.label("distance"),
                Chunk.chunk_metadata.label("metadata"),
            )
            .where(Chunk.embedding.is_not(None))
            .order_by(distance)
            .limit(k)
        )

        if normalized_filters:
            statement = statement.where(Chunk.chunk_metadata.contains(normalized_filters))

        rows = (await self.session.execute(statement)).all()
        return [
            ChunkSearchResult(
                chunk_id=int(row._mapping["chunk_id"]),
                document_id=int(row._mapping["document_id"]),
                chunk_type=str(row._mapping["chunk_type"]),
                content=str(row._mapping["content"]),
                distance=float(row._mapping["distance"]),
                metadata=dict(row._mapping["metadata"] or {}),
            )
            for row in rows
        ]

    async def search_chunks_by_text(
        self,
        *,
        query_text: str,
        k: int,
        metadata_filters: Mapping[str, Any] | None = None,
    ) -> list[ChunkLexicalSearchResult]:
        """Search chunks with PostgreSQL full text ranking.

        This is the lexical branch for Session 10 hybrid retrieval. It uses the
        same text search configuration as the generated ``content_tsv`` column:
        ``english``.
        """

        normalized_filters = _normalize_metadata_filters(metadata_filters)
        content_tsv = literal_column("content_tsv")
        tsquery = func.plainto_tsquery(literal_column("'english'"), query_text)
        rank = func.ts_rank_cd(content_tsv, tsquery)

        statement = (
            select(
                Chunk.id.label("chunk_id"),
                Chunk.document_id.label("document_id"),
                Chunk.chunk_type.label("chunk_type"),
                Chunk.content.label("content"),
                rank.label("rank"),
                Chunk.chunk_metadata.label("metadata"),
            )
            .where(content_tsv.op("@@")(tsquery))
            .order_by(rank.desc(), Chunk.id.asc())
            .limit(k)
        )

        if normalized_filters:
            statement = statement.where(Chunk.chunk_metadata.contains(normalized_filters))

        result = await self.session.execute(statement)

        return [
            ChunkLexicalSearchResult(
                chunk_id=int(row._mapping["chunk_id"]),
                document_id=int(row._mapping["document_id"]),
                chunk_type=str(row._mapping["chunk_type"]),
                content=str(row._mapping["content"]),
                rank=float(row._mapping["rank"]),
                metadata=dict(row._mapping["metadata"] or {}),
            )
            for row in result.all()
        ]
