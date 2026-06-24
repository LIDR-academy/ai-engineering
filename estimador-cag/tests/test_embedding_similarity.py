from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from scripts import compare


def test_cosine_similarity_identical_vectors_equals_one() -> None:
    assert compare.cosine_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal_vectors_equals_zero() -> None:
    assert compare.cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_similarity_zero_vector_does_not_crash() -> None:
    assert compare.cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0
    assert compare.cosine_similarity([1.0, 2.0], [0.0, 0.0]) == 0.0


def test_cosine_similarity_rejects_vectors_with_different_lengths() -> None:
    with pytest.raises(ValueError, match="same length"):
        compare.cosine_similarity([1.0], [1.0, 2.0])


def test_cli_main_embeds_texts_and_prints_similarity(monkeypatch, capsys) -> None:
    class FakeEmbedder:
        def embed_texts(self, texts: list[str]) -> list[list[float]]:
            assert texts == ["OAuth backend", "JWT authorization"]
            return [[1.0, 0.0], [1.0, 0.0]]

    monkeypatch.setattr(compare, "OpenAIEmbedder", FakeEmbedder)

    exit_code = compare.main(
        [
            "--text-a",
            "OAuth backend",
            "--text-b",
            "JWT authorization",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Text A: OAuth backend" in captured.out
    assert "Text B: JWT authorization" in captured.out
    assert "Cosine similarity: 1.0000" in captured.out


def test_compare_script_help_runs_from_file_path() -> None:
    project_root = Path(__file__).resolve().parents[1]

    result = subprocess.run(
        [sys.executable, "scripts/compare.py", "--help"],
        cwd=project_root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Compare two texts with OpenAI embeddings" in result.stdout
