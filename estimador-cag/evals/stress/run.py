"""Session 06 CAG stress runner.

Run against a live FastAPI service:

    python -m evals.stress.run --http http://localhost:8000

The runner writes a CSV plus REPORT.md. It does not optimize the CAG system; it
measures latency, cost, cache behavior, and deterministic memory drift signals.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Any

import httpx

from evals.stress.fixtures.build_pdfs import build_all_pdfs
from evals.stress.metrics import CostBudgetMetric, LatencyBudgetMetric, MemoryDriftMetric
from evals.stress.scenarios import get_scenarios

TURN_OBSERVED_FIELDS = [
    "turn_index",
    "session_id",
    "enriched_transcript_chars",
    "attachments_total_chars",
    "messages_in_window",
    "anchors_count",
    "summary_chars",
    "tokens_in",
    "tokens_out",
    "cost_usd",
    "latency_ms",
    "cache_hit_kind",
    "last_resolved_tier",
]

CSV_FIELDS = [
    "scenario",
    "attachment_size_kb",
    "repeat",
    "fact_to_remember",
    *TURN_OBSERVED_FIELDS,
    "latency_budget_passed",
    "cost_budget_passed",
    "memory_drift_passed",
    "memory_drift_score",
]

TARGET_TURNS = [1, 3, 6, 10, 20]


def _parse_csv_arg(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_int_csv_arg(value: str) -> list[int]:
    return [int(item) for item in _parse_csv_arg(value)]


async def _create_session(client: httpx.AsyncClient) -> str:
    response = await client.post("/sessions")
    response.raise_for_status()
    return str(response.json()["session_id"])


async def _estimate_turn(
    client: httpx.AsyncClient,
    *,
    session_id: str,
    transcript: str,
    attachment_path: Path | None,
) -> dict[str, Any]:
    data = {
        "transcript": transcript,
        "project_type": "web_saas",
        "detail_level": "medium",
        "output_format": "phases_table",
    }
    if attachment_path is None:
        response = await client.post(f"/sessions/{session_id}/estimate", data=data, timeout=120.0)
    else:
        pdf_bytes = attachment_path.read_bytes()
        response = await client.post(
            f"/sessions/{session_id}/estimate",
            data=data,
            files={"attachments": (attachment_path.name, pdf_bytes, "application/pdf")},
            timeout=120.0,
        )
    response.raise_for_status()
    return response.json()


async def _session_snapshot(client: httpx.AsyncClient, session_id: str, response_payload: dict[str, Any]) -> dict[str, Any]:
    try:
        response = await client.get(f"/sessions/{session_id}", timeout=30.0)
        response.raise_for_status()
        snapshot = response.json()
    except httpx.HTTPError:
        snapshot = {}
    snapshot.setdefault("summary", response_payload.get("text", ""))
    snapshot.setdefault("anchors", [])
    return snapshot


async def run_stress(
    *,
    http_base_url: str,
    scenario_names: list[str],
    attachment_sizes: list[int],
    repeats: int,
    output: Path,
    latency_budget_ms: int,
    cost_budget_usd: float,
    turn_count: int,
) -> list[dict[str, Any]]:
    scenarios = get_scenarios(scenario_names)
    requested_sizes = [size for size in attachment_sizes if size > 0]
    generated = build_all_pdfs(sizes_kb=requested_sizes) if requested_sizes else {}
    latency_metric = LatencyBudgetMetric(budget_ms=latency_budget_ms)
    cost_metric = CostBudgetMetric(budget_usd=cost_budget_usd)
    rows: list[dict[str, Any]] = []

    async with httpx.AsyncClient(base_url=http_base_url.rstrip("/")) as client:
        for scenario in scenarios:
            selected_turns = scenario.turns[:turn_count]
            for attachment_size in attachment_sizes:
                attachment_path = generated.get(attachment_size)
                for repeat in range(1, repeats + 1):
                    session_id = await _create_session(client)
                    for turn in selected_turns:
                        turn_attachment_path = attachment_path if turn.turn_index == 1 else None
                        payload = await _estimate_turn(
                            client,
                            session_id=session_id,
                            transcript=turn.transcript,
                            attachment_path=turn_attachment_path,
                        )
                        observation = payload.get("turn_observed") or {}
                        if not observation:
                            snapshot_for_last = await _session_snapshot(client, session_id, payload)
                            observation = snapshot_for_last.get("last_turn_observed") or {}
                        missing = [field for field in TURN_OBSERVED_FIELDS if field not in observation]
                        if missing:
                            raise RuntimeError(f"turn_observed missing fields: {missing}")

                        snapshot = await _session_snapshot(client, session_id, payload)
                        memory_result = MemoryDriftMetric(turn.fact_to_remember).evaluate(snapshot)
                        latency_result = latency_metric.evaluate(observation)
                        cost_result = cost_metric.evaluate(observation)
                        row = {
                            "scenario": scenario.name,
                            "attachment_size_kb": attachment_size,
                            "repeat": repeat,
                            "fact_to_remember": turn.fact_to_remember,
                            **{field: observation[field] for field in TURN_OBSERVED_FIELDS},
                            "latency_budget_passed": latency_result.passed,
                            "cost_budget_passed": cost_result.passed,
                            "memory_drift_passed": memory_result.passed,
                            "memory_drift_score": memory_result.score,
                        }
                        rows.append(row)

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    write_report(rows, output.parent / "REPORT.md")
    return rows


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = int(round((len(ordered) - 1) * 0.95))
    return ordered[index]


def _bool_mean(values: list[Any]) -> float:
    if not values:
        return 0.0
    return sum(1 for value in values if str(value).lower() == "true" or value is True) / len(values)


def _md_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(item) for item in row) + " |")
    return "\n".join(lines)


def write_report(rows: list[dict[str, Any]], path: Path) -> None:
    """Write the mandatory Markdown stress report from CSV rows."""

    by_scenario: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_scenario[str(row["scenario"])].append(row)

    summary_rows: list[list[Any]] = []
    for scenario, scenario_rows in sorted(by_scenario.items()):
        latencies = [float(row["latency_ms"]) for row in scenario_rows]
        costs = [float(row["cost_usd"]) for row in scenario_rows]
        exact_hits = [row["cache_hit_kind"] == "exact" for row in scenario_rows]
        semantic_hits = [row["cache_hit_kind"] == "semantic" for row in scenario_rows]
        recalls = [row["memory_drift_passed"] for row in scenario_rows]
        summary_rows.append(
            [
                scenario,
                len(scenario_rows),
                f"{median(latencies):.1f}",
                f"{_p95(latencies):.1f}",
                f"{sum(costs):.6f}",
                f"{_bool_mean(exact_hits):.2%}",
                f"{_bool_mean(semantic_hits):.2%}",
                f"{_bool_mean(recalls):.2%}",
            ]
        )

    token_buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        tokens = int(float(row["tokens_in"]))
        bucket = f"{(tokens // 1000) * 1000}-{((tokens // 1000) + 1) * 1000 - 1}"
        token_buckets[bucket].append(row)
    latency_curve = []
    for bucket, bucket_rows in sorted(token_buckets.items(), key=lambda item: int(item[0].split("-")[0])):
        latency_curve.append(
            [
                bucket,
                len(bucket_rows),
                f"{median(float(row['latency_ms']) for row in bucket_rows):.1f}",
                f"{_p95([float(row['latency_ms']) for row in bucket_rows]):.1f}",
            ]
        )

    cost_by_turn: dict[int, float] = defaultdict(float)
    count_by_turn: dict[int, int] = defaultdict(int)
    for row in rows:
        turn_index = int(float(row["turn_index"]))
        cost_by_turn[turn_index] += float(row["cost_usd"])
        count_by_turn[turn_index] += 1
    cumulative = 0.0
    cost_curve = []
    for turn_index in sorted(cost_by_turn):
        average_turn_cost = cost_by_turn[turn_index] / max(1, count_by_turn[turn_index])
        cumulative += average_turn_cost
        cost_curve.append([turn_index, f"{average_turn_cost:.8f}", f"{cumulative:.8f}"])

    recall_curve = []
    for target in TARGET_TURNS:
        target_rows = [row for row in rows if int(float(row["turn_index"])) == target]
        if target_rows:
            recall_curve.append([target, len(target_rows), f"{_bool_mean([row['memory_drift_passed'] for row in target_rows]):.2%}"])

    first_turn_cost = cost_by_turn.get(1, 0.0) / max(1, count_by_turn.get(1, 1))
    last_turn = max(cost_by_turn) if cost_by_turn else 1
    last_turn_cost = cost_by_turn.get(last_turn, 0.0) / max(1, count_by_turn.get(last_turn, 1))
    cost_ratio = (last_turn_cost / first_turn_cost) if first_turn_cost else 0.0
    final_recall_turn, _, final_recall = recall_curve[-1] if recall_curve else (0, 0, "0.00%")
    low_recall_after_warmup = next(
        (turn for turn, _, recall in recall_curve if turn >= 3 and float(str(recall).rstrip("%")) < 60.0),
        None,
    )
    recall_claim = (
        f"from turn N={low_recall_after_warmup}, fact recall falls below 60%"
        if low_recall_after_warmup is not None
        else f"at turn N={final_recall_turn}, fact recall is {final_recall}"
    )

    report = f"""# Session 06 CAG stress report

This report is generated from `evals/stress/results.csv`. It measures the existing CAG baseline; it does not optimize prompts, memory limits, provider strategy, or attachment limits.

## Summary table

{_md_table(['scenario', 'rows', 'p50 latency ms', 'p95 latency ms', 'accumulated cost usd', 'exact hit rate', 'semantic hit rate', 'fact recall'], summary_rows)}

## Curve 1: latency vs tokens

{_md_table(['tokens_in bucket', 'rows', 'p50 latency ms', 'p95 latency ms'], latency_curve)}

## Curve 2: cumulative cost vs turn

{_md_table(['turn', 'average turn cost usd', 'cumulative average cost usd'], cost_curve)}

## Curve 3: recall vs N

{_md_table(['N', 'rows', 'fact recall'], recall_curve)}

## Reading

The most important quantitative claim in this run is: {recall_claim}. Another cost claim is: turn {last_turn} average cost is {cost_ratio:.2f} times turn 1 average cost. These claims are intentionally mechanical and reproducible from the CSV, so they can be challenged directly during the live review.

Latency should be read together with `tokens_in` and `attachments_total_chars`, not in isolation. When the 100 KB synthetic attachments are used, extraction and prompt inflation can dominate the turn even if the model path is deterministic. For a live provider run, this same curve is the early warning line for the moment where CAG stops being cheap enough and RAG becomes architecturally attractive.

## Limitations

If `STRESS_FAKE_PROVIDER=true` was used on the backend, token, cost, and latency numbers are deterministic local smoke values, not live provider economics. The runner and observation contract are still valid; rerun against live keys before using the report as a production benchmark.
"""
    path.write_text(report, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Session 06 CAG stress tests")
    parser.add_argument("--http", required=True, help="Base URL of the running FastAPI service")
    parser.add_argument("--scenarios", default="growing,pivot,contradiction")
    parser.add_argument("--attachment-sizes", default="0,5,20,50,100")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", default="evals/stress/results.csv")
    parser.add_argument("--latency-budget-ms", type=int, default=4000)
    parser.add_argument("--cost-budget-usd", type=float, default=0.01)
    parser.add_argument("--turn-count", type=int, default=20)
    return parser.parse_args()


async def async_main() -> None:
    args = parse_args()
    rows = await run_stress(
        http_base_url=args.http,
        scenario_names=_parse_csv_arg(args.scenarios),
        attachment_sizes=_parse_int_csv_arg(args.attachment_sizes),
        repeats=args.repeats,
        output=Path(args.output),
        latency_budget_ms=args.latency_budget_ms,
        cost_budget_usd=args.cost_budget_usd,
        turn_count=args.turn_count,
    )
    print(f"Wrote {len(rows)} rows to {args.output}")
    print(f"Wrote report to {Path(args.output).parent / 'REPORT.md'}")


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
