"""
LAYER: embedding ingestion service
RESPONSIBILITY: Orchestrate chunking, batch embedding, duplicate checks, and persistence.
WHY IT EXISTS: Keeps Session 08 persistent ingest behavior out of FastAPI routers
               so duplicate handling and failure behavior can be tested directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.persistence.repository import EMBEDDING_DIMENSION, ChunkInsert, DocumentRepository


class Chunker(Protocol):
    def chunk(self, budgets: list[Any]) -> list[Any]: ...


class TextEmbedder(Protocol):
    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


@dataclass(frozen=True)
class IngestDocumentCommand:
    """Input command for persistent document ingestion."""

    source_path: str
    document_type: str
    budgets: list[Any]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IngestDocumentResult:
    """Result returned after a successful persistent ingest."""

    document_id: int
    chunks_created: int
    embedding_dimension: int


class DocumentAlreadyIngestedError(Exception):
    """Raised when source_path already exists in persisted documents."""

    def __init__(self, *, document_id: int) -> None:
        super().__init__("Document already ingested")
        self.document_id = document_id


class PersistentEmbeddingIngestionService:
    """Application service for Session 08 persistent embedding ingestion."""

    def __init__(
        self,
        *,
        chunker: Chunker,
        embedder: TextEmbedder,
        repository: DocumentRepository,
    ) -> None:
        self.chunker = chunker
        self.embedder = embedder
        self.repository = repository

    async def ingest_document(self, command: IngestDocumentCommand) -> IngestDocumentResult:
        """Persist one document and its embedded chunks.

        The service deliberately calls the embedder before repository insertion.
        That keeps provider failures from creating orphan documents. Transaction
        wrapping will be added at the FastAPI/session boundary in a later slice.
        """
        existing_document_id = await self.repository.find_document_id_by_source_path(
            command.source_path
        )
        if existing_document_id is not None:
            raise DocumentAlreadyIngestedError(document_id=existing_document_id)

        chunks = self.chunker.chunk(command.budgets)
        texts = [chunk.text for chunk in chunks]
        embeddings = self.embedder.embed_texts(texts)

        if len(embeddings) != len(chunks):
            raise ValueError("Embedding count mismatch")

        chunk_rows = [
            ChunkInsert(
                chunk_type="budget_component",
                content=chunk.text,
                embedding=embedding,
                metadata={
                    **dict(chunk.metadata),
                    "chunk_id": chunk.chunk_id,
                    "token_count": chunk.token_count,
                },
            )
            for chunk, embedding in zip(chunks, embeddings, strict=True)
        ]

        document_id = await self.repository.add_document_with_chunks(
            source_path=command.source_path,
            document_type=command.document_type,
            chunks=chunk_rows,
            metadata=command.metadata,
        )

        return IngestDocumentResult(
            document_id=document_id,
            chunks_created=len(chunk_rows),
            embedding_dimension=EMBEDDING_DIMENSION,
        )
