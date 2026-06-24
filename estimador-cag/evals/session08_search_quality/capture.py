"""
Capture utility for Session 08 search-quality responses.

This script calls an already-running FastAPI /search endpoint for the canonical
Session 08 cases, validates the response shape, and writes captured responses
atomically. It keeps runtime evidence generation separate from committed reports
so accidental partial writes do not corrupt evaluation artifacts.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from evals.session08_search_quality.evaluator import (
    DEFAULT_CASES_PATH,
    SearchQualityCase,
    evaluate_response_map,
    load_cases,
    render_markdown_report,
    summarize_evaluations,
)

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_TOP_K = 5
DEFAULT_TIMEOUT_SECONDS = 120

PostSearchFn = Callable[
    [str, dict[str, Any], float],
    dict[str, Any],
]


def build_search_payload(case: SearchQualityCase, *, top_k: int) -> dict[str, Any]:
    """Build the POST /search request payload for one quality case."""
    query = case.query.strip()
    if not query:
        raise ValueError(f"{case.case_id}: query must not be empty")
    if top_k <= 0:
        raise ValueError("top_k must be positive")

    return {
        "query": query,
        "k": top_k,
    }


def capture_responses(
    *,
    cases: Sequence[SearchQualityCase],
    base_url: str,
    top_k: int,
    timeout_seconds: float,
    post_search_fn: Callable[..., dict[str, Any]] = None,
) -> dict[str, dict[str, Any]]:
    """Capture one /search response per case using an injectable HTTP function."""
    post_search = post_search_fn or post_search_response
    responses_by_case_id: dict[str, dict[str, Any]] = {}

    for case in cases:
        response = post_search(
            base_url=base_url,
            payload=build_search_payload(case, top_k=top_k),
            timeout_seconds=timeout_seconds,
        )
        responses_by_case_id[case.case_id] = response

    validate_response_map(cases=cases, responses_by_case_id=responses_by_case_id)
    return responses_by_case_id


def post_search_response(
    *,
    base_url: str,
    payload: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    """Call POST /search and return the decoded JSON payload."""
    url = f"{base_url.rstrip('/')}/search"
    request_body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url=url,
        data=request_body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8")
        raise RuntimeError(
            f"POST {url} failed with HTTP {exc.code}: {error_body}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"POST {url} failed: {exc}") from exc

    parsed = json.loads(body)
    if not isinstance(parsed, dict):
        raise ValueError(f"POST {url} did not return a JSON object")

    parsed["_client_elapsed_ms"] = int((time.perf_counter() - started) * 1000)
    return parsed


def validate_response_map(
    *,
    cases: Sequence[SearchQualityCase],
    responses_by_case_id: dict[str, dict[str, Any]],
) -> None:
    """Validate captured response map before writing it to disk."""
    expected_case_ids = {case.case_id for case in cases}
    actual_case_ids = set(responses_by_case_id)

    for case_id in sorted(expected_case_ids - actual_case_ids):
        raise ValueError(f"Missing captured response for case_id={case_id}")

    for case_id in sorted(actual_case_ids - expected_case_ids):
        raise ValueError(f"Unexpected captured response for case_id={case_id}")

    for case in cases:
        response = responses_by_case_id[case.case_id]
        if not isinstance(response, dict):
            raise ValueError(f"{case.case_id}: response must be a JSON object")

        results = response.get("results")
        if not isinstance(results, list):
            raise ValueError(f"{case.case_id}: results must be a list")

        for index, result in enumerate(results, start=1):
            if not isinstance(result, dict):
                raise ValueError(f"{case.case_id}: result {index} must be a JSON object")

            metadata = result.get("metadata", {})
            if metadata is not None and not isinstance(metadata, dict):
                raise ValueError(f"{case.case_id}: result {index} metadata must be an object")

            if "distance" in result:
                _coerce_distance(case.case_id, index, result["distance"])


def write_json_atomically(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON through a sibling temp file and replace the target atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = Path(str(path) + ".tmp")
    tmp_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(path)


def write_report_from_responses(
    *,
    cases: Sequence[SearchQualityCase],
    responses_by_case_id: dict[str, dict[str, Any]],
    report_path: Path,
) -> None:
    """Evaluate captured responses and write a markdown report."""
    validate_response_map(cases=cases, responses_by_case_id=responses_by_case_id)
    evaluations = evaluate_response_map(
        cases=list(cases),
        responses_by_case_id=responses_by_case_id,
    )
    summary = summarize_evaluations(evaluations)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        render_markdown_report(summary=summary, evaluations=evaluations),
        encoding="utf-8",
    )


def _coerce_distance(case_id: str, result_index: int, value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{case_id}: result {result_index} distance must be numeric"
        ) from exc


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Capture Session 08 /search responses for offline quality evaluation."
    )
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument(
        "--base-url",
        default=os.getenv("SESSION08_BASE_URL", DEFAULT_BASE_URL),
    )
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="JSON file to write captured responses into.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="Optional markdown report path generated from captured responses.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print cases and payloads without calling /search or writing files.",
    )
    args = parser.parse_args(argv)

    cases = load_cases(args.cases)

    if args.dry_run:
        print("Dry run only. No /search calls and no files written.")
        print(f"Base URL: {args.base_url}")
        print(f"Top K: {args.top_k}")
        for case in cases:
            print(json.dumps(build_search_payload(case, top_k=args.top_k), ensure_ascii=False))
        return 0

    responses_by_case_id = capture_responses(
        cases=cases,
        base_url=args.base_url,
        top_k=args.top_k,
        timeout_seconds=args.timeout_seconds,
    )
    write_json_atomically(args.output, responses_by_case_id)

    if args.report:
        write_report_from_responses(
            cases=cases,
            responses_by_case_id=responses_by_case_id,
            report_path=args.report,
        )

    print(f"Wrote captured responses: {args.output}")
    if args.report:
        print(f"Wrote evaluation report: {args.report}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
