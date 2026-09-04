## Context

See `proposal.md` - Why. The data path exists twice over, and the analogs are discarded
at two different points. The Rails side:

```
per-task hours response -> run.task_hours (JSONB, stored verbatim, keeps "neighbors")
  -> run.task_hours_view -> Rag::TaskHoursEstimateView#tasks[].neighbors
     (Rag::TaskNeighborView, already parsed; #closeness_pct already exists)
     -- used before this change ONLY for the summary counters at the top --

  -> seed_breakdown_with_hours(modules, result)  [controller.rb:181]
       -> run.adjusted_breakdown (JSONB) -> run.adjusted_modules
          -> Rag::WorkModuleView -> Rag::TaskItemView   (no "neighbors" attribute)
          -- THIS is what `_step_hours.html.erb` iterates to render the per-task rows --
```

`run.adjusted_modules` is the row source because it also carries the module grouping and
`task.description` (echoed from the human-reviewed structure), neither of which
`Rag::TaskHoursEstimateView#tasks` carries. Switching the row source would lose the
module tree and the descriptions; that is not on the table.

The AI service side, discovered by the adversarial review:

```
run_task_hours_recovery_agent
  -> derive_task_hours(args)          [agent_tools.py:230] args.neighbors: 4 fields, validated
       returns {module, task, estimated_hours, reliability, dispersion, has_match, summary}
       -- the neighbors are used for the consensus and then DROPPED (only counted in a log) --
  -> agent_loop.py:284  AgentTaskDerivation(module, task, estimated_hours, reliability,
                                            has_match)      -- no neighbors field to hold them --
  -> agent_estimation.py:192  est.model_copy(update={estimated_hours, reliability,
                                                     has_match: True, hours_range: None})
     -- neighbors never set, so the stored payload is has_match:true + neighbors:[] --
```

## Goals / Non-Goals

**Goals:**
- Get `neighbors` from `run.task_hours_view` to the row-rendering loop that already
  iterates `run.adjusted_modules`, without changing what that loop iterates.
- Make an agent-recovered task arrive with the analogs the agent actually used.
- Make "hours with no analog detail" a visible state rather than an invisible one.

**Non-Goals:**
- Do not add `neighbors` to `adjusted_breakdown` / `Rag::TaskItemView`. That would let
  analog data ride into the persisted, confirmed estimate even though the `verification`
  step is out of scope - a field present but unused there is exactly the kind of scope
  creep the out-of-scope list was written to prevent.
- Do not change the LLM-facing tool schema, add a retrieval call, or change what the
  agent sees. The analogs are already in its tool arguments.
- Do not relocate `Rag::TaskNeighborView#closeness_pct` (see Decisions below).
- Do not surface `budget_id` / `source_id` in the UI.

## Decisions

### Where the module/task join lives

**Decision:** one read-only method on `Rag::EstimationRun`,
`task_hours_neighbors_by_task`, building a
`{ [module_name, task_name] => Array<Rag::TaskNeighborView> }` index from
`task_hours_view.tasks` (empty hash when `task_hours` is blank). `_step_hours.html.erb`
looks up `[mod.name, task.name]` per row.

**Why:** `Rag::EstimationRun` is already the home for this exact shape of glue -
`task_hours_view`, `adjusted_modules`, `sync_review_flag!` all live there, each reading
one JSONB column and handing the view a typed object. A model method keeps the ERB free
of hash-building logic.

**Alternative considered - copy `neighbors` into `seed_breakdown_with_hours`:** rejected.
It means `adjusted_breakdown` - the JSONB that becomes the confirmed, persisted estimate -
carries analog data that no screen renders, a second source of truth drifting into a place
this change was not asked to touch.

**Known, accepted risk:** the lookup key is `[module_name, task_name]`, a string-equality
join. `seed_breakdown_with_hours` already keys itself the same way (`controller.rb:190`),
so this is an established pattern, not a new fragility. A join miss now degrades into the
*labelled* unavailable-detail state below rather than into silence.

### The recovery agent's analogs are recorded, not recomputed

**Decision:** `derive_task_hours` echoes the neighbors it was given in its return value;
`AgentTaskDerivation` gains `neighbors: list[DeriveTaskHoursNeighbor]`; `agent_loop.py`
populates it from that return value; `agent_estimation.py` carries it into the merge.

**Why:** the data is already there and already validated. `DeriveTaskHoursNeighbor`
(`agent_schemas.py:79`) carries `estimated_hours`, `distance`, `source_id` and
`budget_id` — every field `TaskNeighbor` has — and the strict tool schema marks all four
required. Nothing needs to be searched again, re-embedded, or inferred; the fix is to
stop throwing away a value the consensus already consumed.

**Safety property:** the agent's observation is
`result.get("summary") or result.get("error") or json.dumps(result)[:200]`
(`agent_loop.py:292`), and `summary` is always present on a successful
`derive_task_hours`. Adding a `neighbors` key to the returned dict therefore never
reaches the model: no context growth, no token cost, no behavioural drift in the loop.
This is why the change is safe to make inside a live agent path.

**Where the type mapping goes — forced by the layering rule.** `ARCHITECTURE.md` forbids
a `generation/` sibling importing another, so `generation/agentic` must NOT import
`generation/rag/schemas.TaskNeighbor`. Hence `AgentTaskDerivation.neighbors` is typed with
the agentic-local `DeriveTaskHoursNeighbor`, and the
`DeriveTaskHoursNeighbor -> TaskNeighbor` conversion happens in the **conductor**,
`app/domain/agent_estimation.py`, which already imports both sides (it imports
`build_result` from `generation/rag/task_hours` today). The architecture picks the seam
for us.

### `TaskNeighbor.source_id` becomes optional

**Decision:** `source_id: int` -> `int | None = None`.

**Why:** `DeriveTaskHoursNeighbor.source_id` is already `int | None`, because an analog
the agent reports may not carry a corpus chunk id. Three options were considered:
relax the field, drop analogs lacking an id, or require the agent to always supply one.
Dropping them silently discards evidence that genuinely backed the consensus; requiring
the id makes the response depend on the model copying a field faithfully. Relaxing it is
the honest model of what the data is. The UI is unaffected — it renders only hours and
closeness — and `Rag::TaskNeighborView` already tolerates a nil `source_id`.

**Blast radius:** widening a response field from required to optional is backward
compatible for readers. Rails parses with explicit keys and renders neither id.

### `closeness_pct` stays in `business-backend`

**Decision:** reuse `Rag::TaskNeighborView#closeness_pct` as it exists today; do not move
the `distance -> 0..100` conversion into `ai-service`.

**Why:** `docs/business-backend-standards.md` flags exactly this shape ("a `0..100` score
computed in a Ruby view object is domain logic that leaked into presentation") as
something to decide and state explicitly - so here it is: the helper already exists, is
already exercised by the summary counters this change does not touch, and relocating it is
an unrelated change. This change already reverses one scope decision on evidence; it does
not need to relitigate a second one without any.

### Unavailable analog detail is labelled, not silent

**Decision:** render a distinct, muted "sin detalle de análogos" indication when a task
reports a match but carries no analogs — visually distinct from the red "sin análogo
histórico".

**Why:** this is the state that hid the recovery-path bug. A row that renders *nothing*
is indistinguishable from a row whose analogs are simply below the fold, so neither a
user nor a reviewer can tell "no precedent exists" from "precedent exists and was
dropped". After the AI service fix the state is rarer but still reachable — legacy
payloads, and the accepted module/task rename join miss — and it must stay legible.

## Risks / Trade-offs

- [A task/module is renamed between the `review` and `hours` steps] -> Mitigation: the
  join miss now degrades into the labelled unavailable-detail state instead of silence,
  so it is visible when it happens. `seed_breakdown_with_hours` has the identical string-key
  dependency today, so no new failure mode is introduced.
- [Touching a live agent path could change agent behaviour] -> Mitigation: the safety
  property above (the extra key never reaches the model's observation), pinned by a test
  asserting the observation string is unchanged.
- [Reviewers expect the `verification` step to also show analogs] -> Mitigation: still out
  of scope; a separate follow-up would extend `task_hours_neighbors_by_task` reuse there.

## Migration Plan

No data migration, no schema migration, no new dependency. Two deploys' worth of code in
one change; the layers are independently deployable in either order:

- Rails deployed first: recovered tasks show the new "sin detalle de análogos" label
  (an honest improvement over rendering nothing) until the service ships.
- Service deployed first: the extra `neighbors` in the payload are simply parsed and not
  yet rendered.

Older `Rag::EstimationRun` rows keep rendering the unavailable-detail label wherever
`neighbors` was never recorded. Runs already advanced past the `hours` step are not
backfilled.
