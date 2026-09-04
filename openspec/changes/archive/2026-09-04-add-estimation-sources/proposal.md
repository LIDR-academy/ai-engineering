## Why

The `hours` step of the RAG estimation wizard already grounds every task's hours in
historical analogs (`TaskNeighbor`, already parsed on the Rails side into
`Rag::TaskNeighborView`), but no template renders them. The estimator sees a number with
no evidence behind it and has to trust it blind. Surfacing the analogs closes that gap
with data the system already computes.

An independent adversarial review of the first implementation found that closing the gap
on the Rails side alone is not enough, because the analogs are discarded **twice**, one
layer apart:

- The wizard's `hours` step calls only `RagEstimateClient#agent_estimate_task_hours`
  (`Rag::EstimationRunsController#estimate_hours`); the deterministic
  `#estimate_task_hours` this change was originally specified against has no caller
  anywhere in the app.
- On that agent path, `app/domain/agent_estimation.py` merges the recovery agent's
  result onto the deterministic estimate without carrying `neighbors` — and
  `AgentTaskDerivation` has no `neighbors` field to carry, even though the agent's own
  `derive_task_hours` arguments already contain every field `TaskNeighbor` needs.

So a task rescued by the recovery agent is stored as a match with an empty analog list
and renders hours plus a reliability badge with **no evidence and no explanation** —
visually identical to a well-grounded task. Those are precisely the rows whose numbers
most need justifying. This change therefore also fixes the AI service, reversing the
original "no `ai-service` change" scope decision, which was made before the second
discard was known.

## What Changes

- The `hours` step (`app/views/rag/estimation_runs/_step_hours.html.erb`) renders,
  under each task, the list of historical task analogs it was derived from
  (`estimated_hours` + `closeness_pct`), in the order the API returned them.
- A task with no historical match shows an explicit "sin análogo histórico" message
  instead of an analog list.
- A task that has derived hours but no analog detail (a payload predating this change, or
  a module/task rename losing the join) now shows a **distinct, muted** "sin detalle de
  análogos" indication instead of rendering nothing. Silence is what let the recovery-path
  gap hide.
- The AI service carries the recovery agent's analogs through to the response, so an
  agent-grounded task arrives with its analogs instead of an empty list.
- `TaskNeighbor.source_id` becomes optional: an agent-sourced analog may legitimately
  have no corpus chunk id, and dropping such an analog would discard real evidence.

## Capabilities

### New Capabilities

- `rag/task-hours-explainability`: the `hours` step of the RAG estimation wizard shows,
  per task, the historical task analogs (hours + closeness) its estimate was derived
  from — including tasks grounded by the recovery agent — so the estimator can judge the
  number instead of trusting it blind, and is told plainly when the supporting detail is
  unavailable.

### Modified Capabilities

- None. This introduces a new, previously unspecified requirement; it does not change
  the behavior of an existing spec'd capability (no living spec exists yet for the RAG
  wizard's `hours` step).

## Impact

- `business-backend/app/views/rag/estimation_runs/_step_hours.html.erb` — renders the
  analog block per task, plus the new unavailable-detail indication.
- `business-backend/app/models/rag/estimation_run.rb` — adds
  `task_hours_neighbors_by_task`, the module/task → neighbors lookup (see `design.md`).
  `Rag::EstimationRunsController` is NOT changed — `seed_breakdown_with_hours` /
  `adjusted_breakdown` stay untouched by design.
- `business-backend/app/models/rag/task_hours_estimate_view.rb`,
  `app/models/rag/task_neighbor_view.rb` — already provide the parsed data
  (`tasks[].neighbors`, `closeness_pct`); no change expected.
- `ai-service/app/generation/rag/schemas.py` — `TaskNeighbor.source_id` becomes optional.
- `ai-service/app/generation/agentic/agent_tools.py`,
  `app/generation/agentic/agent_schemas.py`,
  `app/generation/agentic/agent_loop.py` — the recovery agent's derivation records the
  analogs it used instead of only their count.
- `ai-service/app/domain/agent_estimation.py` — the merge carries those analogs onto the
  merged estimate. The agentic → RAG type mapping lives here, in the conductor, because
  `generation/` siblings may not import each other (see `design.md`).
- **No `docs/contract/business-backend-consumed-routes.json` change.** That file pins
  `{client, method, path}` and `scripts/check_contract.py` verifies route + verb
  existence and probe exemption, not response fields. The contract that moves here is the
  Pydantic response schema; the pinned route list is unaffected, and the contract check
  must still pass.
- **No LLM-facing tool-schema change and no added token cost** — the analogs are already
  in the agent's tool arguments today; only what the service records changes.
