# Requirement: Show the historical task analogs behind each hours estimate

> Output of the `close-requirement` skill. No open decisions may survive into this
> document. Written in English.
>
> **Revision (post adversarial review).** The first version of this requirement scoped
> `ai-service` out on the belief that the analogs already reached the client for every
> task. An independent review disproved that for the agent-recovery path, which is the
> only path the wizard uses. The scope decision is reversed below, on evidence.

## Story

As the wizard user estimating a project (the instructor/estimator running
`Rag::EstimationRun`),
I want to see, for each task on the "Horas por tarea" screen, which historical tasks its
estimated hours were derived from,
so that I can judge whether to trust the number instead of treating it as an opaque
output.

## Objective

Surface, on the existing `hours` step of the RAG estimation wizard, the historical task
analogs (`TaskNeighbor`) behind every task whose hours were derived — including the tasks
the recovery agent grounded — and say so plainly when that supporting detail is
unavailable.

## Context

`ai-service`'s per-task hours search (`app/generation/rag/task_hours.py::estimate_one`)
builds one `TaskNeighbor` (`source_id`, `budget_id`, `estimated_hours`, `distance`) per
matched historical task and attaches the list as `TaskHoursEstimate.neighbors`
(`app/generation/rag/schemas.py:725,773`). The response travels into `business-backend`'s
`task_hours` JSONB column, and `Rag::TaskHoursEstimateView` already parses it into
`Rag::TaskNeighborView` objects (`app/models/rag/task_hours_estimate_view.rb:26`), which
already expose a `closeness_pct` helper (`app/models/rag/task_neighbor_view.rb:20`).

None of it is rendered. `app/views/rag/estimation_runs/_step_hours.html.erb` builds its
task rows from `run.adjusted_modules`, seeded by
`Rag::EstimationRunsController#seed_breakdown_with_hours` (line 181), which drops
`neighbors`, and from `Rag::TaskItemView`, which has no attribute for them. The parsed
`Rag::TaskNeighborView` objects are reachable only through `run.task_hours_view`, used
today solely for the summary counters.

**What the adversarial review added to this picture.** The wizard's `hours` step calls
only `RagEstimateClient#agent_estimate_task_hours`
(`Rag::EstimationRunsController#estimate_hours:95`); the deterministic
`#estimate_task_hours` has no caller in the app. On that path
`app/domain/agent_estimation.py:192` merges the recovery agent's result with
`model_copy(update={estimated_hours, reliability, has_match: True, hours_range: None})`
and never sets `neighbors`, and `AgentTaskDerivation` (`agent_schemas.py:163`) has no
`neighbors` field to carry them. So an agent-recovered task is stored as a match with an
empty analog list, and renders hours plus a reliability badge with no evidence and no
explanation. Reproduced against the real view: a recovered task rendered `32 h` and
`55% fiab.` with neither an analog list nor the "no analog" message.

The analogs are nevertheless present at the agent's tool boundary:
`DeriveTaskHoursNeighbor` (`agent_schemas.py:79`) already carries all four fields
`TaskNeighbor` needs, and the strict tool schema marks them required. They are validated,
consumed by the consensus, and then discarded. So this remains an "expose", not a
"calculate" — at two layers instead of one.

## Scope

### In scope

- The `hours` step of the wizard (`_step_hours.html.erb` and the view/controller glue
  needed to make each task row carry its `neighbors`).
- Rendering, for every task reported as matched, the full list of analogs the API
  returned (`estimated_hours` + `closeness_pct`), in the order received.
- Rendering an explicit "no historical analog" message for unmatched tasks.
- Rendering a distinct "unavailable analog detail" indication for a task that has hours
  but no analogs, replacing today's silent empty render.
- Tasks with a contradicted consensus (`hours_range` present) also render their analogs.
- `ai-service`: carrying the recovery agent's analogs through
  `derive_task_hours` -> `AgentTaskDerivation` -> the merge in `agent_estimation.py`, so
  an agent-grounded task arrives with its analogs.
- `ai-service`: making `TaskNeighbor.source_id` optional.

### Out of scope

- The `verification` step and the confirmed `adjusted_breakdown` (analogs are not
  propagated there in this change).
- The `/v1/estimate/from-transcript`, graph (`/v1/estimate/graph`) and supervisor
  (`/v1/estimate/supervisor`) paths.
- Any change to the LLM-facing tool schemas, to what the agent observes, or to the
  retrieval the agent performs. No new API field beyond the `source_id` nullability
  change; no new endpoint.
- Exposing `budget_id` or `source_id` as a clickable/citable reference in the UI.
- Relocating `closeness_pct` out of `Rag::TaskNeighborView`. It stays a presentation-layer
  computation, a deliberate exception noted against `docs/business-backend-standards.md`,
  accepted because the helper already exists and relocating it is a separate change.
- Backfilling analogs for estimation runs confirmed or advanced past the `hours` step
  before this change ships.

## Closed decisions

- Solution shape: extend existing behavior on the `hours` step, and stop the AI service
  discarding the agent's analogs. No new endpoint, no new retrieval, no change to the
  agent's tool schema.
- Layer ownership: **both layers** (revised). `business-backend` owns the rendering;
  `ai-service` owns carrying the recovery agent's analogs into the response. The original
  "`ai-service` untouched" decision was made without knowledge of the second discard and
  is superseded.
- Type mapping placement: the `DeriveTaskHoursNeighbor -> TaskNeighbor` conversion lives
  in the conductor (`app/domain/agent_estimation.py`), because `ARCHITECTURE.md` forbids
  `generation/agentic` importing `generation/rag`.
- `TaskNeighbor.source_id` becomes `int | None`. An agent-sourced analog may have no
  corpus chunk id; dropping such analogs would discard real evidence, and requiring the id
  would make the response depend on the model copying a field faithfully.
- Persistence: no new persistence and no migration. `task_hours` JSONB already stores the
  full API response.
- Backward compatibility: widening `source_id` from required to optional is compatible for
  readers. Rails parses with explicit keys. Older `Rag::EstimationRun` rows whose
  `task_hours` lacks `neighbors` must render the unavailable-detail label, not raise.
- Degradation: no new external call is introduced; the data source is already present
  whenever the `hours` step renders.
- Authorization: unchanged — any user who can reach `Rag::EstimationRun#show` sees its
  analogs. No new authorization boundary.

## Expected behavior

- Normal: a matched task shows its analogs (one row per `TaskNeighbor`, in API order)
  with `estimated_hours` and `closeness_pct`, always visible, without extra clicks.
- Agent-recovered: a task the deterministic pass could not ground and the agent could
  shows its analogs exactly like a deterministically matched task.
- Edge case — contradicted consensus (`hours_range` present): analogs still render in
  full; they are the evidence for the shown range.
- Edge case — no match: the analog block is replaced by an explicit "sin análogo
  histórico" message; no empty list is shown.
- Edge case — hours present, analogs absent (payload predates this change, or the
  module/task join missed): a distinct "sin detalle de análogos" indication renders. No
  error, and never a silent blank.
- Edge case — an analog with a null `source_id`: rendered normally; the UI shows only
  hours and closeness.
- Edge case — the agent searched and still found nothing: the task stays unmatched and
  keeps the red "sin análogo histórico" message.
- Failure — `run.task_hours` is blank: unchanged from today — the step redirects the user
  back to "Revisión" before any task row is rendered.

## Expected output

Per task row on the `hours` step, an analog block driven by data inside `task_hours`.

| Field | Type | Nullable | Source of truth | If missing |
| ----- | ---- | -------- | --------------- | ---------- |
| `neighbors[].estimated_hours` | integer | no (per entry) | `TaskNeighbor.estimated_hours` inside the stored `task_hours` JSONB | entry absent from the list |
| `neighbors[].closeness_pct` | integer (0-100) | no (per entry) | derived from `TaskNeighbor.distance` via `Rag::TaskNeighborView#closeness_pct` | entry absent from the list |
| `neighbors[].source_id` | integer | **yes** (revised) | `TaskNeighbor.source_id` | not rendered (out of scope) |
| `neighbors[].budget_id` | string | yes | `TaskNeighbor.budget_id` | not rendered (out of scope) |
| task-level "no analog" flag | boolean | no | `TaskHoursEstimate.has_match` (`false` ⇒ show the red message) | n/a — always present when the task was estimated |
| task-level "no detail" state | derived | n/a | matched task whose `neighbors` list is empty or absent | shows the muted unavailable-detail indication |

## Success criteria

- On the `hours` step, every matched task visibly lists its historical analogs (hours +
  closeness %) without any additional user interaction — **including tasks grounded by
  the recovery agent**.
- Every unmatched task shows the explicit "sin análogo histórico" message and no analog
  list.
- A matched task with no analog data renders the distinct unavailable-detail indication,
  without error, and is not confusable with the unmatched case.
- The merged per-task hours response carries the agent's analogs for every task the agent
  grounded; a task the agent could not ground stays unmatched.
- The agent's observed tool output is unchanged, proving no behavioural drift in the loop.
- `bin/rails test` passes with controller-test coverage (`assert_select`, asserting on
  text unique to an analog row) for matched, contradicted, unmatched, agent-recovered and
  no-detail cases.
- `uv run pytest` passes with coverage of the merge carrying `neighbors` and of a null
  `source_id` serializing.
- `uv run python scripts/check_contract.py` still passes — the pinned route contract is
  unaffected.

## Open questions

- None. (If this section is not empty, the requirement is not closed.)
