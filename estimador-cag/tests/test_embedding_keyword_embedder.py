from app.embedding_pipeline.keyword_embedder import KeywordTextEmbedder


def test_keyword_text_embedder_returns_one_vector_per_text() -> None:
    embedder = KeywordTextEmbedder()

    vectors = embedder.embed_texts(
        [
            "OAuth JWT authentication",
            "inventory synchronization",
        ]
    )

    assert len(vectors) == 2
    assert len(vectors[0]) == len(embedder.keywords)
    assert vectors[0] != vectors[1]


def test_keyword_text_embedder_is_case_insensitive_and_deterministic() -> None:
    embedder = KeywordTextEmbedder()

    lower_vector = embedder.embed_texts(["oauth jwt token"])[0]
    upper_vector = embedder.embed_texts(["OAUTH JWT TOKEN"])[0]

    assert lower_vector == upper_vector
