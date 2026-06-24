"""
LAYER: embedding pipeline reranking
RESPONSIBILITY: Provide second-stage reranking for retrieved chunks.
WHY IT EXISTS: Session 10 compares recall-then-rerank retrieval variants while
               keeping normal CI deterministic and free from model downloads.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any, Protocol

from app.embedding_pipeline.search_service import SearchResultItem

DEFAULT_CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


class CrossEncoderModel(Protocol):
    """Minimal interface implemented by sentence-transformers CrossEncoder."""

    def predict(
        self,
        sentences: Sequence[tuple[str, str]],
        *,
        batch_size: int = 32,
        show_progress_bar: bool = False,
    ) -> Sequence[float]:
        """Return one relevance score per query-document pair."""


class KeywordOverlapReranker:
    """Deterministic query-token overlap reranker.

    This is the CI-safe fallback. It keeps the reranker branch executable when
    sentence-transformers is not installed or model download is not desired.
    """

    def rerank(
        self,
        *,
        query: str,
        items: list[SearchResultItem],
        top_n: int,
    ) -> list[SearchResultItem]:
        """Return candidates ordered by normalized query token overlap."""

        if top_n <= 0:
            raise ValueError("top_n must be positive")

        query_terms = _tokenize(query)
        if not query_terms:
            return items[:top_n]

        scored = sorted(
            enumerate(items),
            key=lambda indexed_item: (
                -_overlap_score(query_terms, indexed_item[1].content),
                indexed_item[0],
            ),
        )
        return [item for _, item in scored[:top_n]]


class CrossEncoderReranker:
    """Model-backed cross-encoder reranker.

    The cross-encoder scores each `(query, retrieved_chunk)` pair jointly. This
    follows the Session 10 recall-then-rerank pattern: retrieve a wider candidate
    pool first, score candidates with a cross-encoder, then keep the highest
    scoring items.

    The actual sentence-transformers model is loaded lazily only when this class
    is instantiated without an injected model, so normal CI can test the logic
    without downloading weights.
    """

    def __init__(
        self,
        *,
        model_name: str = DEFAULT_CROSS_ENCODER_MODEL,
        model: CrossEncoderModel | None = None,
        device: str | None = None,
        batch_size: int = 32,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")

        self.model_name = model_name
        self.batch_size = batch_size
        self.model = model if model is not None else _load_cross_encoder(model_name, device=device)

    def rerank(
        self,
        *,
        query: str,
        items: list[SearchResultItem],
        top_n: int,
    ) -> list[SearchResultItem]:
        """Return candidates ordered by cross-encoder relevance score."""

        if top_n <= 0:
            raise ValueError("top_n must be positive")
        if not items:
            return []

        pairs = [(query, item.content) for item in items]
        raw_scores = self.model.predict(
            pairs,
            batch_size=self.batch_size,
            show_progress_bar=False,
        )
        scores = [float(score) for score in raw_scores]

        if len(scores) != len(items):
            raise ValueError("cross-encoder score count mismatch")

        ranked = sorted(
            enumerate(items),
            key=lambda indexed_item: (-scores[indexed_item[0]], indexed_item[0]),
        )
        return [item for _, item in ranked[:top_n]]


def _load_cross_encoder(model_name: str, *, device: str | None) -> CrossEncoderModel:
    try:
        from sentence_transformers import CrossEncoder
    except ImportError as exc:
        raise RuntimeError(
            "CrossEncoderReranker requires the local-embeddings extra. "
            "Install it with: uv sync --extra local-embeddings --extra dev"
        ) from exc

    kwargs: dict[str, Any] = {}
    if device:
        kwargs["device"] = device
    return CrossEncoder(model_name, **kwargs)


def _tokenize(text: str) -> set[str]:
    return {match.group(0).lower() for match in _TOKEN_RE.finditer(text)}


def _overlap_score(query_terms: set[str], content: str) -> float:
    content_terms = _tokenize(content)
    if not content_terms:
        return 0.0
    return len(query_terms & content_terms) / len(query_terms)
