"""
CLI helper for Session 07 embedding sanity checks.

It embeds two texts with OpenAIEmbedder and prints their cosine similarity.
The similarity calculation deliberately uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import math
import sys
from collections.abc import Sequence
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.embedding_pipeline.embedder import OpenAIEmbedder  # noqa: E402


def cosine_similarity(vector_a: Sequence[float], vector_b: Sequence[float]) -> float:
    """Compute cosine similarity without numpy or scikit-learn."""
    if len(vector_a) != len(vector_b):
        raise ValueError("Vectors must have the same length")

    norm_a = math.sqrt(sum(value * value for value in vector_a))
    norm_b = math.sqrt(sum(value * value for value in vector_b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    dot_product = sum(
        value_a * value_b for value_a, value_b in zip(vector_a, vector_b, strict=True)
    )
    return dot_product / (norm_a * norm_b)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare two texts with OpenAI embeddings and cosine similarity."
    )
    parser.add_argument("--text-a", required=True, help="First text to embed")
    parser.add_argument("--text-b", required=True, help="Second text to embed")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    embeddings = OpenAIEmbedder().embed_texts([args.text_a, args.text_b])
    similarity = cosine_similarity(embeddings[0], embeddings[1])

    print(f"Text A: {args.text_a}")
    print(f"Text B: {args.text_b}")
    print(f"Cosine similarity: {similarity:.4f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
