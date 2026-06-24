"""
LAYER: persistence models
RESPONSIBILITY: Define SQLAlchemy models for persisted documents and chunks.
WHY IT EXISTS: Session 08 needs a typed bridge between the embedding pipeline
               and the PostgreSQL plus pgvector schema.
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base metadata for Session 08 persistence models."""


class Document(Base):
    """One ingested historical budget document."""

    __tablename__ = "documents"
    __table_args__ = (
        sa.Index("ix_documents_source_path", "source_path", unique=True),
    )

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    source_path: Mapped[str] = mapped_column(sa.Text, nullable=False)
    document_type: Mapped[str] = mapped_column(sa.String(length=50), nullable=False)
    ingested_at: Mapped[Any] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        nullable=False,
    )
    document_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        postgresql.JSONB(astext_type=sa.Text()),
        server_default=sa.text("'{}'::jsonb"),
        nullable=False,
    )

    chunks: Mapped[list[Chunk]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Chunk(Base):
    """One searchable chunk belonging to an ingested document."""

    __tablename__ = "chunks"
    __table_args__ = (
        sa.Index("ix_chunks_document_id", "document_id"),
        sa.Index("ix_chunks_chunk_type", "chunk_type"),
        sa.Index("ix_chunks_metadata_gin", "metadata", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    document_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_type: Mapped[str] = mapped_column(sa.String(length=50), nullable=False)
    content: Mapped[str] = mapped_column(sa.Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    chunk_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        postgresql.JSONB(astext_type=sa.Text()),
        server_default=sa.text("'{}'::jsonb"),
        nullable=False,
    )
    created_at: Mapped[Any] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        nullable=False,
    )

    document: Mapped[Document] = relationship(back_populates="chunks")
