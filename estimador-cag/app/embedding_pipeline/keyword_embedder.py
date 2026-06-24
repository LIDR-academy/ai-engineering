"""
LAYER: embedding_pipeline keyword embedder
RESPONSIBILITY: Provide a deterministic fake text embedder for local chunking labs.
WHY IT EXISTS: Session 07 live plus needs retrieval-shaped comparisons without
               live OpenAI calls, database persistence, or flaky tests.
"""


class KeywordTextEmbedder:
    """Deterministic fake embedder for local chunking comparison reports."""

    keywords = [
        "oauth",
        "jwt",
        "authorization",
        "token",
        "authentication",
        "banking",
        "audit",
        "consent",
        "checkout",
        "payment",
        "inventory",
        "stock",
        "document",
        "clinical",
        "upload",
        "telemetry",
        "machine",
        "alert",
        "maintenance",
        "dashboard",
    ]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Return simple keyword-count vectors, one vector per text."""
        vectors: list[list[float]] = []

        for text in texts:
            lower_text = text.lower()
            vectors.append(
                [float(lower_text.count(keyword)) for keyword in self.keywords]
            )

        return vectors
