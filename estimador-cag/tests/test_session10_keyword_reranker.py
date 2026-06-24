from app.embedding_pipeline.reranker import KeywordOverlapReranker
from app.embedding_pipeline.search_service import SearchResultItem


def _item(chunk_id: int, content: str) -> SearchResultItem:
    return SearchResultItem(
        chunk_id=chunk_id,
        document_id=100 + chunk_id,
        chunk_type="budget_component",
        content=content,
        distance=float(chunk_id),
        metadata={"budget_id": f"BUD-{chunk_id}"},
    )


def test_keyword_overlap_reranker_promotes_query_term_matches():
    reranker = KeywordOverlapReranker()

    result = reranker.rerank(
        query="OAuth banking authentication",
        items=[
            _item(1, "Generic backend implementation"),
            _item(2, "OAuth banking authentication and audit logging"),
            _item(3, "Frontend dashboard polish"),
        ],
        top_n=2,
    )

    assert [item.chunk_id for item in result] == [2, 1]


def test_keyword_overlap_reranker_is_stable_for_ties():
    reranker = KeywordOverlapReranker()

    result = reranker.rerank(
        query="banking",
        items=[
            _item(1, "banking backend"),
            _item(2, "banking authentication"),
            _item(3, "unrelated frontend"),
        ],
        top_n=3,
    )

    assert [item.chunk_id for item in result] == [1, 2, 3]


def test_keyword_overlap_reranker_caps_to_top_n():
    reranker = KeywordOverlapReranker()

    result = reranker.rerank(
        query="OAuth banking authentication",
        items=[
            _item(1, "Generic backend implementation"),
            _item(2, "OAuth banking authentication"),
            _item(3, "banking authentication"),
        ],
        top_n=1,
    )

    assert [item.chunk_id for item in result] == [2]
