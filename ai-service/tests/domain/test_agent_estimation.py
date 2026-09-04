"""Tests for the Session 12 conductor (agentic + rag composition).

Network-free: the agent entrypoints and the deterministic ``estimate_all`` are
stubbed, so the focus is the conductor's own logic — the structure→Estimate
mapping and the HYBRID merge (deterministic first, agent recovery only on the
flagged tasks, merge back).
"""

from __future__ import annotations

import app.domain.agent_estimation as conductor
from app.domain.agent_estimation import _structure_to_estimate, agent_estimate_task_hours
from app.domain.schemas.agent_trace import AgentStep, AgentTrace
from app.generation.agentic.agent_schemas import (
    AgentModuleNode,
    AgentStructure,
    AgentTaskDerivation,
    AgentTaskHoursRun,
    AgentTaskNode,
    DeriveTaskHoursNeighbor,
)
from app.generation.rag.schemas import (
    TaskHoursEstimate,
    TaskHoursModuleInput,
    TaskHoursResult,
    TaskHoursTaskInput,
    TaskNeighbor,
)


# --- structure → Estimate mapping ------------------------------------------ #
def test_structure_maps_to_ungrounded_hourless_estimate():
    structure = AgentStructure(
        modules=[
            AgentModuleNode(
                name="Auth",
                description="Access",
                tasks=[AgentTaskNode(name="OAuth backend", description="JWT")],
            )
        ],
        confidence="high",
        reasoning="Standard.",
    )
    estimate = _structure_to_estimate(structure)
    assert estimate.total_engineer_days is None
    assert estimate.confidence == "high"
    task = estimate.modules[0].tasks[0]
    assert task.engineer_days is None
    assert task.grounded is False
    assert task.sources == []


def test_empty_structure_becomes_insufficient():
    structure = AgentStructure(modules=[], confidence="low", reasoning="Too vague.")
    estimate = _structure_to_estimate(structure)
    assert estimate.confidence == "insufficient"
    assert estimate.modules == []
    assert estimate.insufficient_context_explanation == "Too vague."


# --- hybrid merge ---------------------------------------------------------- #
def _modules():
    return [
        TaskHoursModuleInput(
            name="Auth",
            tasks=[TaskHoursTaskInput(name="OAuth backend"), TaskHoursTaskInput(name="RBAC")],
        )
    ]


def _base_result() -> TaskHoursResult:
    # One well-grounded task, one with no match → only the second should be flagged.
    return TaskHoursResult(
        tasks=[
            TaskHoursEstimate(
                module="Auth",
                task="OAuth backend",
                estimated_hours=120,
                reliability=0.8,
                has_match=True,
            ),
            TaskHoursEstimate(module="Auth", task="RBAC", has_match=False),
        ]
    )


async def test_hybrid_recovers_only_flagged_and_merges(monkeypatch):
    async def fake_estimate_all(modules, *, top_k=None, distance_threshold=None):
        return _base_result()

    recovery_seen: dict = {}

    async def fake_recovery(flagged, **kwargs):
        recovery_seen["flagged"] = [(t.module, t.task) for t in flagged]
        return AgentTaskHoursRun(
            derivations=[
                AgentTaskDerivation(
                    module="Auth", task="RBAC", estimated_hours=64, reliability=0.55, has_match=True
                )
            ],
            trace=AgentTrace(
                steps=[AgentStep(step=1, tool="search_budgets", tool_args={}, observation="found")]
            ),
            iterations=3,
            stopped_reason="completed",
        )

    monkeypatch.setattr(conductor, "estimate_all", fake_estimate_all)
    monkeypatch.setattr(conductor, "run_task_hours_recovery_agent", fake_recovery)

    result = await agent_estimate_task_hours(_modules(), client=object(), model="gpt-5-mini")

    # Only the no-match task was handed to the agent.
    assert recovery_seen["flagged"] == [("Auth", "RBAC")]
    by_task = {t.task: t for t in result.tasks}
    # The already-grounded task is untouched.
    assert by_task["OAuth backend"].estimated_hours == 120
    # The flagged task was overwritten with the agent's recovered hours.
    assert by_task["RBAC"].estimated_hours == 64
    assert by_task["RBAC"].has_match is True
    assert result.agent_trace.steps  # the recovery trace rode back


async def test_hybrid_skips_agent_when_nothing_flagged(monkeypatch):
    async def fake_estimate_all(modules, *, top_k=None, distance_threshold=None):
        return TaskHoursResult(
            tasks=[
                TaskHoursEstimate(
                    module="Auth",
                    task="OAuth backend",
                    estimated_hours=120,
                    reliability=0.9,
                    has_match=True,
                )
            ]
        )

    called = {"recovery": False}

    async def fake_recovery(flagged, **kwargs):
        called["recovery"] = True
        return AgentTaskHoursRun(derivations=[], trace=AgentTrace(), iterations=0)

    monkeypatch.setattr(conductor, "estimate_all", fake_estimate_all)
    monkeypatch.setattr(conductor, "run_task_hours_recovery_agent", fake_recovery)

    result = await agent_estimate_task_hours(_modules(), client=object(), model="gpt-5-mini")

    assert called["recovery"] is False  # zero extra cost in the happy path
    assert result.agent_trace is not None
    assert result.agent_trace.steps == []  # empty-step trace = "no recovery needed"


async def test_hybrid_recovered_task_carries_its_analogs(monkeypatch):
    """The adversarial-review finding: an agent-recovered task must not merge in
    with an empty analog list. The agent's derive_task_hours args already carry
    every field TaskNeighbor needs; the merge must not discard them."""

    async def fake_estimate_all(modules, *, top_k=None, distance_threshold=None):
        return _base_result()

    async def fake_recovery(flagged, **kwargs):
        return AgentTaskHoursRun(
            derivations=[
                AgentTaskDerivation(
                    module="Auth",
                    task="RBAC",
                    estimated_hours=64,
                    reliability=0.55,
                    has_match=True,
                    neighbors=[
                        DeriveTaskHoursNeighbor(
                            estimated_hours=60, distance=0.2, source_id=9, budget_id="B-9"
                        ),
                        DeriveTaskHoursNeighbor(
                            estimated_hours=68, distance=0.3, source_id=None, budget_id=None
                        ),
                    ],
                )
            ],
            trace=AgentTrace(),
            iterations=1,
            stopped_reason="completed",
        )

    monkeypatch.setattr(conductor, "estimate_all", fake_estimate_all)
    monkeypatch.setattr(conductor, "run_task_hours_recovery_agent", fake_recovery)

    result = await agent_estimate_task_hours(_modules(), client=object(), model="gpt-5-mini")
    by_task = {t.task: t for t in result.tasks}

    recovered = by_task["RBAC"]
    assert recovered.has_match is True
    assert len(recovered.neighbors) == 2
    assert [n.estimated_hours for n in recovered.neighbors] == [60, 68]
    assert recovered.neighbors[0].source_id == 9
    assert recovered.neighbors[1].source_id is None  # optional, per design.md

    # The already-grounded task's own neighbors are untouched by the merge.
    assert by_task["OAuth backend"].neighbors == []


async def test_hybrid_keeps_deterministic_when_agent_finds_nothing(monkeypatch):
    async def fake_estimate_all(modules, *, top_k=None, distance_threshold=None):
        return _base_result()

    async def fake_recovery(flagged, **kwargs):
        # The agent searched but grounded nothing.
        return AgentTaskHoursRun(
            derivations=[AgentTaskDerivation(module="Auth", task="RBAC", has_match=False)],
            trace=AgentTrace(),
            iterations=2,
            stopped_reason="completed",
        )

    monkeypatch.setattr(conductor, "estimate_all", fake_estimate_all)
    monkeypatch.setattr(conductor, "run_task_hours_recovery_agent", fake_recovery)

    result = await agent_estimate_task_hours(_modules(), client=object(), model="gpt-5-mini")
    by_task = {t.task: t for t in result.tasks}
    assert by_task["RBAC"].has_match is False  # unchanged; no fabricated hours
    assert by_task["RBAC"].estimated_hours is None


# --- Session 16: the output guardrail survives the merge -------------------- #
def _thin_evidence_result() -> TaskHoursResult:
    """Twelve tasks all leaning on one historical component: flagged by breadth."""
    return TaskHoursResult(
        tasks=[
            TaskHoursEstimate(
                module="Auth",
                task=f"task {i}",
                estimated_hours=40,
                reliability=0.8,
                has_match=True,
                neighbors=[TaskNeighbor(source_id=1, estimated_hours=40, distance=0.2)],
            )
            for i in range(12)
        ]
    )


async def test_the_guardrail_verdict_is_present_when_no_recovery_runs(monkeypatch):
    async def fake_estimate_all(modules, *, top_k=None, distance_threshold=None):
        return _thin_evidence_result()

    monkeypatch.setattr(conductor, "estimate_all", fake_estimate_all)
    result = await agent_estimate_task_hours(_modules(), client=object(), model="gpt-5-mini")

    assert result.requires_human_review is True
    assert result.review_reasons


async def test_the_guardrail_is_re_run_over_the_merged_hours(monkeypatch):
    """The early return and the post-merge return are two different constructions.

    Both build a fresh ``TaskHoursResult``, so a verdict computed once upstream
    would be silently dropped by whichever path ran — and it would be dropped at
    precisely the moment the numbers changed. This pins the second path.
    """

    async def fake_estimate_all(modules, *, top_k=None, distance_threshold=None):
        base = _thin_evidence_result()
        # One task with no match, so recovery actually runs.
        base.tasks.append(TaskHoursEstimate(module="Auth", task="RBAC", has_match=False))
        return base

    async def fake_recovery(flagged, **kwargs):
        return AgentTaskHoursRun(
            derivations=[
                AgentTaskDerivation(
                    module="Auth",
                    task="RBAC",
                    estimated_hours=64,
                    reliability=0.55,
                    has_match=True,
                )
            ],
            trace=AgentTrace(),
            iterations=1,
            stopped_reason="completed",
        )

    monkeypatch.setattr(conductor, "estimate_all", fake_estimate_all)
    monkeypatch.setattr(conductor, "run_task_hours_recovery_agent", fake_recovery)

    result = await agent_estimate_task_hours(_modules(), client=object(), model="gpt-5-mini")

    assert {t.task for t in result.tasks} >= {"RBAC"}
    assert result.requires_human_review is True
    assert any("distinct historical analogs" in r for r in result.review_reasons)
