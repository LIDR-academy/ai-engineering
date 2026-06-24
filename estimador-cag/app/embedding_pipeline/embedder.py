"""
LAYER: embedding_pipeline embedder
RESPONSIBILITY: Convert structural chunks or raw texts into OpenAI embedding vectors.
WHY IT EXISTS: Session 07 needs an in-memory vectorization foundation before retrieval,
               pgvector persistence, model comparisons, or RAG are introduced.
"""

from __future__ import annotations

import os
import time
from typing import Protocol

import structlog
import tiktoken
from openai import OpenAI, OpenAIError, RateLimitError

from app.embedding_pipeline.schemas import Chunk, EmbeddedChunk

EMBEDDING_MODEL = "text-embedding-3-small"

# Exercise statement price. Verify against official OpenAI pricing before production use.
EMBEDDING_PRICE_USD_PER_1M_TOKENS = 0.02

DEFAULT_BATCH_SIZE = 100
RATE_LIMIT_BACKOFF_SECONDS = (1, 2, 4)

logger = structlog.get_logger(__name__)


class EmbeddingsResource(Protocol):
    def create(self, *, model: str, input: list[str]): ...


class EmbeddingClient(Protocol):
    embeddings: EmbeddingsResource


def estimate_embedding_cost_usd(total_tokens: int) -> float:
    """Estimate input embedding cost using the exercise statement price."""
    return (total_tokens / 1_000_000) * EMBEDDING_PRICE_USD_PER_1M_TOKENS


def _encoding_for_embedding_model(model: str):
    """Return the tokenizer used for embedding token accounting."""
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        return tiktoken.get_encoding("cl100k_base")


def count_embedding_tokens(texts: list[str], model: str = EMBEDDING_MODEL) -> int:
    """Count input tokens with the embedding tokenizer, not character length."""
    encoding = _encoding_for_embedding_model(model)
    return sum(len(encoding.encode(text)) for text in texts)


class OpenAIEmbedder:
    """
    OpenAI embeddings adapter.

    The optional client parameter is intentional. It keeps normal CI deterministic by
    allowing tests to inject fake clients instead of calling the live OpenAI API.
    """

    def __init__(
        self,
        *,
        client: EmbeddingClient | None = None,
        model: str = EMBEDDING_MODEL,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")

        self.client = client or OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = model
        self.batch_size = batch_size

    def embed_one(self, text: str) -> list[float]:
        """Embed one text using the same batch path as multi-text calls."""
        return self.embed_texts([text])[0]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed raw texts in batches while preserving input order."""
        if not texts:
            return []

        embeddings: list[list[float]] = []

        for batch in self._batched(texts):
            response = self._create_embeddings_with_retry(batch)
            embeddings.extend([list(item.embedding) for item in response.data])

        return embeddings

    def embed_many(self, chunks: list[Chunk]) -> list[EmbeddedChunk]:
        """Embed structural chunks and preserve every chunk field."""
        if not chunks:
            return []

        embeddings = self.embed_texts([chunk.text for chunk in chunks])

        return [
            EmbeddedChunk(
                chunk_id=chunk.chunk_id,
                text=chunk.text,
                metadata=chunk.metadata,
                token_count=chunk.token_count,
                embedding=embedding,
            )
            for chunk, embedding in zip(chunks, embeddings, strict=True)
        ]

    def _batched(self, texts: list[str]) -> list[list[str]]:
        return [texts[index : index + self.batch_size] for index in range(0, len(texts), self.batch_size)]

    def _create_embeddings_with_retry(self, texts: list[str]):
        batch_token_count = count_embedding_tokens(texts, model=self.model)
        last_rate_limit_error: RateLimitError | None = None

        for attempt_index in range(len(RATE_LIMIT_BACKOFF_SECONDS) + 1):
            started = time.perf_counter()

            try:
                response = self.client.embeddings.create(model=self.model, input=texts)
            except RateLimitError as exc:
                last_rate_limit_error = exc
                if attempt_index >= len(RATE_LIMIT_BACKOFF_SECONDS):
                    logger.warning(
                        "embedding_batch_rate_limited",
                        chunk_count=len(texts),
                        token_count=batch_token_count,
                        model=self.model,
                        attempts=attempt_index + 1,
                    )
                    raise

                time.sleep(RATE_LIMIT_BACKOFF_SECONDS[attempt_index])
                continue
            except OpenAIError:
                logger.exception(
                    "embedding_batch_failed",
                    chunk_count=len(texts),
                    token_count=batch_token_count,
                    model=self.model,
                )
                raise
            except Exception:
                logger.exception(
                    "embedding_batch_failed",
                    chunk_count=len(texts),
                    token_count=batch_token_count,
                    model=self.model,
                )
                raise

            latency_ms = int((time.perf_counter() - started) * 1000)
            logger.info(
                "embedding_batch_completed",
                chunk_count=len(texts),
                token_count=batch_token_count,
                latency_ms=latency_ms,
                model=self.model,
            )
            return response

        if last_rate_limit_error is not None:
            raise last_rate_limit_error

        raise RuntimeError("Embedding batch failed without an exception")
