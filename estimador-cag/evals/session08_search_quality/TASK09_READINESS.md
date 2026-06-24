# Session 08 to Task 09 Readiness Bridge

status: session08-live-inspired-bridge
branch: gg-session-08-live-inspired-hardening
scope: Session 08 hardening artifact that prepares Task 09 without implementing Task 09

## Source status

The official Task 09 statement is still the stronger source of truth once it is uploaded or pasted.

This bridge is not a Task 09 implementation.
This bridge is not a benchmark superiority claim.
This bridge is not production readiness evidence.

It exists to preserve what Session 08 now contributes to the next evaluation and quality task.

## Why this bridge exists

Session 08 created and hardened the RAG retrieval foundation:

- PostgreSQL plus pgvector persistence
- Alembic documents and chunks schema
- persistent ingest
- semantic `/search`
- cosine-distance retrieval
- metadata filters
- HNSW cosine vector index
- browser and Streamlit search paths
- search metrics
- offline search-quality evaluator
- safe search-response capture utility

Task 09 should build on this foundation by evaluating whether retrieval and generated answers are useful, grounded, and safe.

## Reusable Session 08 artifacts

| Artifact | Reuse value for Task 09 |
| --- | --- |
| `evals/session08_search_quality/cases.jsonl` | Seed retrieval-quality cases and expected component IDs. |
| `evals/session08_search_quality/evaluator.py` | Deterministic top-k hit, expected-rank, and negative-control scoring. |
| `evals/session08_search_quality/capture.py` | Safe response capture utility with atomic JSON writing. |
| `evals/session08_search_quality/REPORT.md` | Example report structure and scope boundaries. |
| README search-quality workflow | Human-readable command path for dry-run, capture, and offline scoring. |

## Mapping to likely Task 09 deliverables

| Likely Task 09 deliverable | Session 08 bridge status | Next Task 09 action |
| --- | --- | --- |
| Evaluation dataset or test set | Partially covered for retrieval cases. | Create official Task 09 cases after reading the official task statement. |
| Repeatable evaluation runner or script | Partially covered for captured `/search` responses. | Add Task 09 runner for generated answers and RAG outputs. |
| Metrics for answer quality or retrieval quality | Retrieval quality exists. Answer quality does not. | Add deterministic answer-quality metrics. |
| At least one regression case | Negative-control retrieval case exists. | Add generated-answer regression cases. |
| Hallucination or unsupported-claim detection | Not implemented. | Add deterministic unsupported-claim checks over answer evidence. |
| Grounding or evidence-coverage checks | Not implemented for answers. | Add claim-to-evidence coverage checks. |
| Generated evaluation report | Retrieval report shape exists. | Add Task 09 report with results, failure analysis, and limitations. |
| README documentation | Session 08 workflow documented. | Document Task 09 eval suite and interpretation rules. |
| Deterministic tests | Covered for Session 08 evaluator and capture utility. | Add Task 09 dataset, metrics, runner, and report tests. |
| Normal CI compatibility with fake provider keys | Preserved. | Keep Task 09 normal tests deterministic and fake-key compatible. |

## Missing Task 09 work

The following items should remain for the dedicated Task 09 branch:

- Official Task 09 statement ingestion
- Generated answer evaluation
- Grounding checks over answer claims
- Unsupported-claim detection
- Requirement coverage metrics
- Format compliance metrics
- Task 09 evaluation report
- Task 09 README section
- Optional live-provider smoke separated from deterministic CI

## Forbidden claims

Do not claim:

- full Task 09 completion
- production readiness
- benchmark superiority
- hallucination detection solved
- grounding solved
- better-than-frontier-model performance
- teacher-live implementation copied or merged

Allowed claim:

- Session 08 now has a deterministic retrieval-quality bridge that can seed Task 09 evaluation work.

## Recommended Task 09 branch

Use a dedicated Task 09 branch:

    gg-session-09-evaluation-quality

If the teacher requires a canonical branch name, keep the dual-branch strategy:

    gg-session-09-evaluation-quality
    session-09/pre-work or the exact required official branch

## First Task 09 slice

Slice 1: official Task 09 audit and dataset schema

Non-goals:

- No LLM calls
- No live provider dependency
- No benchmark claims
- No retrieval tuning
- No Energy Aware product implementation

Acceptance:

- official Task 09 source is documented or explicitly marked pending
- JSONL dataset schema exists
- parser validates valid cases
- parser rejects invalid cases
- deterministic tests pass
- README or Task 09 report explains the scope

## Suggested Task 09 sequence

1. Official task audit and dataset schema.
2. Deterministic answer-quality metrics.
3. Evaluation runner over fixture outputs.
4. Retrieval and grounding bridge over `/search`.
5. Unsupported-claim detection.
6. Report and README documentation.
7. Optional bounded live smoke outside normal CI.

## Decision JSON

{
  "decision": "accept_bridge",
  "branch": "gg-session-08-live-inspired-hardening",
  "bridge_scope": "Session 08 retrieval-quality artifacts prepared for Task 09 evaluation and quality work",
  "hard_reject_violations": [],
  "hard_repair_violations": [],
  "limitations": [
    "official Task 09 statement is still pending",
    "answer-quality evaluation is not implemented here",
    "grounding and unsupported-claim checks are not implemented here",
    "no benchmark superiority is claimed"
  ],
  "next_action": "start_task09_on_dedicated_branch_after_official_task_statement_audit"
}
