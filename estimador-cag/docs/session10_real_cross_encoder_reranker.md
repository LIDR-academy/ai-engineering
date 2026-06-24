# Session 10 real cross-encoder reranking

This branch keeps normal CI deterministic, but it now also includes a real model-backed reranker path.

## What was added

- `CrossEncoderReranker` in `app/embedding_pipeline/reranker.py`.
- A CI-safe unit test that injects a fake scoring model and proves cross-encoder ordering logic without downloading model weights.
- `evals/session10_retrieval/run_cross_encoder.py`, a manual A/B/C/D runner that uses a sentence-transformers `CrossEncoder` for configurations C and D.

## Why it is manual

The real cross-encoder can download model weights and may be slow or unavailable in constrained CI environments. For that reason, normal CI still uses the deterministic keyword reranker. The real reranker is available through an explicit manual command.

## How to run locally

Install the optional local embeddings extra:

    cd estimador-cag
    uv sync --extra dev --extra local-embeddings

Run the real cross-encoder A/B/C/D measurement:

    uv run python -m evals.session10_retrieval.run_cross_encoder --k 5 --recall-k 8

Optional CPU-only run:

    uv run python -m evals.session10_retrieval.run_cross_encoder --k 5 --recall-k 8 --device cpu

Default model:

    cross-encoder/ms-marco-MiniLM-L-6-v2

Outputs are intentionally local and ignored by git:

    evals/session10_retrieval/results_cross_encoder.local.json
    evals/session10_retrieval/REPORT_CROSS_ENCODER.local.md

## Current limitation

I could not run the real model-backed command in Codespaces after the quota was exhausted. The committed code integrates the real reranker path and CI validates the ordering logic through an injected scorer, but the real model latency numbers must be generated manually when compute is available.
