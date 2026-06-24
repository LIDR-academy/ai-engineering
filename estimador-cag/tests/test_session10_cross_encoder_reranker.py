from collections.abc import Sequence

import pytest

from app.embedding_pipeline.reranker import CrossEncoderReranker
from app.embedding_pipeline.search_service import SearchResultItem


class ScoringModel:
    def __init__(self, scores: Sequence[float]) -> None:
        self.scores = list(scores)
        self.pairs: list[tuple[tuple[str, str], ...]] = []

    def predict(
        self,
        sentences: Sequence[tuple[str, str]],
        *,
        batch_size: int = 32,
        show_progress_bar: bool = False,
    ) -> list[float]:
        self.pairs.append(tuple(sentences))
        return self.scores


def _item(chunk_id: int, content: str) -> SearchResultItem:
    return SearchResultItem(
        chunk_id=chunk_id,
        document_id=chunk_id,
        chunk_type="budget_component",
        content=content,
        distance=float(chunk_id),
        metadata={"component_id": str(chunk_id)},
    )


def test_cross_encoder_reranker_orders_by_model_score() -> None:
    model = ScoringModel([0.2, 0.95, 0.4])
    reranker = CrossEncoderReranker(model=model)

    result = reranker.rerank(
        query="banking authentication",
        items=[
            _item(1, "generic backend"),
            _item(2, "OAuth banking authentication"),
            _item(3, "audit logging"),
        ],
        top_n=2,
    )

    assert [item.chunk_id for item in result] == [2, 3]
    assert model.pairs == [
        (
            ("banking authentication", "generic backend"),
            ("banking authentication", "OAuth banking authentication"),
            ("banking authentication", "audit logging"),
        )
    ]


def test_cross_encoder_reranker_preserves_input_order_for_ties() -> None:
    model = ScoringModel([0.5, 0.5, 0.1])
    reranker = CrossEncoderReranker(model=model)

    result = reranker.rerank(
        query="banking",
        items=[
            _item(1, "first candidate"),
            _item(2, "second candidate"),
            _item(3, "third candidate"),
        ],
        top_n=3,
    )

    assert [item.chunk_id for item in result] == [1, 2, 3]


def test_cross_encoder_reranker_validates_score_count() -> None:
    model = ScoringModel([0.9])
    reranker = CrossEncoderReranker(model=model)

    with pytest.raises(ValueError, match="score count mismatch"):
        reranker.rerank(
            query="banking",
            items=[_item(1, "one"), _item(2, "two")],
            top_n=2,
        )
