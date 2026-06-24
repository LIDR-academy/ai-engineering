"""
Session 08 query examples.

Run through Docker Compose after the API service is up:

    docker compose up -d postgres redis ai_service
    docker compose run --rm ai_service uv run python query_examples.py --dry-run
    docker compose run --rm ai_service uv run python query_examples.py

The non-dry run calls POST /search for the required five example queries.
It expects the corpus to have been ingested already, or it can ingest the local
example corpus first with --ingest-example-corpus.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any

DEFAULT_BASE_URL = "http://ai_service:8000"
DEFAULT_TOP_K = 5

REQUIRED_QUERIES = [
    "REST API development with JWT authentication for financial sector",
    "secure backend service with token-based access control for banking applications",
    "mobile application for restaurant reservations",
    "integration with external system",
    "migration from monolith to microservices architecture using Kubernetes",
]

EXAMPLE_BUDGET = {
    "budget_id": "BUD-SESSION08-EXAMPLE",
    "client_metadata": {
        "name": "FintechCorp",
        "sector": "finance",
        "country": "ES",
    },
    "project_summary": (
        "Fintech modernization project with REST APIs, JWT authentication, "
        "external integrations, Kubernetes migration, and an operations dashboard."
    ),
    "main_technology": "python",
    "year": 2024,
    "total_estimated_hours": 520,
    "components": [
        {
            "component_id": "AUTH-001",
            "name": "JWT authentication API",
            "description": (
                "REST API development with JWT authentication, token refresh, "
                "role-based authorization, and financial-sector security controls."
            ),
            "tech_stack": ["python", "fastapi", "postgresql", "redis"],
            "estimated_hours": 140,
            "complexity": "high",
            "dependencies": [],
        },
        {
            "component_id": "INT-001",
            "name": "External payment provider integration",
            "description": (
                "Integration with external banking and payment systems, including "
                "webhook handling, retry logic, and audit logging."
            ),
            "tech_stack": ["python", "fastapi", "postgresql"],
            "estimated_hours": 120,
            "complexity": "medium",
            "dependencies": ["AUTH-001"],
        },
        {
            "component_id": "MIG-001",
            "name": "Kubernetes migration",
            "description": (
                "Migration from monolith to microservices architecture using Kubernetes, "
                "containerized services, health checks, and deployment automation."
            ),
            "tech_stack": ["docker", "kubernetes", "python"],
            "estimated_hours": 180,
            "complexity": "high",
            "dependencies": ["AUTH-001", "INT-001"],
        },
        {
            "component_id": "UI-001",
            "name": "Operations dashboard",
            "description": (
                "Internal dashboard for operations teams to monitor audit events, "
                "integration status, and financial workflow health."
            ),
            "tech_stack": ["typescript", "react"],
            "estimated_hours": 80,
            "complexity": "medium",
            "dependencies": ["INT-001"],
        },
    ],
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Session 08 /search query examples.")
    parser.add_argument(
        "--base-url",
        default=os.getenv("SESSION08_BASE_URL", DEFAULT_BASE_URL),
        help="Base URL for the running FastAPI service.",
    )
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the required queries without calling the API.",
    )
    parser.add_argument(
        "--ingest-example-corpus",
        action="store_true",
        help="Call /embeddings/ingest once before running /search.",
    )
    args = parser.parse_args()

    print("Session 08 query examples")
    print(f"Base URL: {args.base_url}")
    print(f"Top K: {args.top_k}")
    print()

    if args.dry_run:
        print("Dry run only. Required queries:")
        for index, query in enumerate(REQUIRED_QUERIES, start=1):
            print(f"{index}. {query}")
        return 0

    if args.ingest_example_corpus:
        _ingest_example_corpus(base_url=args.base_url)

    for index, query in enumerate(REQUIRED_QUERIES, start=1):
        _print_search_results(
            index=index,
            query=query,
            response=_post_json(
                url=f"{args.base_url.rstrip('/')}/search",
                payload={"query": query, "k": args.top_k},
            ),
        )

    return 0


def _ingest_example_corpus(*, base_url: str) -> None:
    print("Ingesting example corpus...")
    try:
        response = _post_json(
            url=f"{base_url.rstrip('/')}/embeddings/ingest",
            payload={
                "source_path": "examples/session08/query_examples_budget.json",
                "document_type": "historical_budget",
                "content": {"budgets": [EXAMPLE_BUDGET]},
            },
        )
    except RuntimeError as exc:
        message = str(exc)
        if "409" in message and "Document already ingested" in message:
            print("Example corpus already ingested.")
            print()
            return
        raise

    print(json.dumps(response, indent=2, ensure_ascii=False))
    print()


def _post_json(*, url: str, payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url=url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8")
        raise RuntimeError(f"POST {url} failed with HTTP {exc.code}: {error_body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"POST {url} failed: {exc}") from exc

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    parsed = json.loads(response_body)
    parsed["_client_elapsed_ms"] = elapsed_ms
    return parsed


def _print_search_results(*, index: int, query: str, response: dict[str, Any]) -> None:
    print("=" * 88)
    print(f"Query {index}: {query}")
    print(f"Server search_time_ms: {response.get('search_time_ms')}")
    print(f"Client elapsed_ms: {response.get('_client_elapsed_ms')}")
    print(f"Results returned: {len(response.get('results', []))}")
    print()

    for rank, result in enumerate(response.get("results", []), start=1):
        content = str(result.get("content", "")).replace("\\n", " ")
        preview = content[:120]

        print(
            f"{rank}. chunk_id={result.get('chunk_id')} "
            f"distance={float(result.get('distance')):.4f} "
            f"chunk_type={result.get('chunk_type')}"
        )
        print(f"   content={preview}")
        print(f"   metadata={json.dumps(result.get('metadata', {}), ensure_ascii=False)}")
        print()

    if not response.get("results"):
        print("No results.")
        print()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
