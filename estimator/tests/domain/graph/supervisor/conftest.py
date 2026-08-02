"""Shared doubles for the Session 14 supervisor tests.

Every test in this package runs with NO network and NO API key: the LLM wrapper, the
retrieval backend and the consensus function are replaced at the same module-level
seams the production code imports them from.
"""

from __future__ import annotations

from statistics import mean

import pytest

from app.domain.graph.schemas import (
    ComponentClassification,
    ConsolidatedEstimate,
    RequirementsExtraction,
    SupervisorDecision,
)

TRANSCRIPT = "A" * 200
CONFIG = {"configurable": {"thread_id": "s14-test"}}

# The full dependency-order route. Tests pass this explicitly so the run is driven by
# the "model" rather than by a default — which is the property under test. An EMPTY
# script means the wrapper answers "finish" on the first call, so the graph would go
# straight to the gate without dispatching anyone.
FULL_ROUTE = [
    "requirements_extractor",
    "budget_searcher",
    "estimate_generator",
    "coherence_validator",
    "finish",
]


class FakeWrapper:
    """A scripted ``LLMWrapper`` that dispatches on ``response_model`` identity.

    ``route_script`` drives the supervisor: one target per call. Once exhausted it
    returns ``"finish"``. Driving the route from a script is how these tests
    demonstrate that routing is model-driven — the graph obeys whatever order the
    "model" asks for, rather than a hard-coded sequence.
    """

    def __init__(
        self,
        *,
        route_script: list[str] | None = None,
        requirements: list[str] | None = None,
        components: list[tuple[str, str]] | None = None,
        estimate: dict | None = None,
        route_error: Exception | None = None,
    ) -> None:
        self.route_script = list(route_script or [])
        self.requirements = requirements or ["req one", "req two"]
        self.components = components or [("API", "backend"), ("App", "mobile")]
        self.estimate = estimate
        self.route_error = route_error
        self.calls: list[str] = []

    def complete_structured(self, *, response_model, **kwargs):
        self.calls.append(response_model.__name__)

        if response_model is SupervisorDecision:
            if self.route_error is not None:
                raise self.route_error
            target = self.route_script.pop(0) if self.route_script else "finish"
            return (
                SupervisorDecision(
                    next_agent=target, reason=f"scripted route to {target}", confidence="high"
                ),
                {},
            )

        if response_model is RequirementsExtraction:
            return RequirementsExtraction(requirements=self.requirements), {}

        if response_model is ComponentClassification:
            return (
                ComponentClassification(
                    components=[{"name": n, "category": c} for n, c in self.components]
                ),
                {},
            )

        if response_model is ConsolidatedEstimate:
            payload = self.estimate or {
                "components": [
                    {"name": n, "engineer_days": 10, "rationale": "from references"}
                    for n, _ in self.components
                ],
                "total_engineer_days": 10 * len(self.components),
                "confidence": "high",
                "reasoning": "consolidated from the anchors",
            }
            return ConsolidatedEstimate(**payload), {}

        raise AssertionError(f"unexpected response_model: {response_model!r}")


def backend_factory(hours_by_component: dict[str, list[int]]):
    """A ``make_retrieval_backend`` replacement returning canned historical items.

    The query the agent builds is ``"<name> (<category>)"``, so the component name is
    recovered by splitting on the parenthesis.
    """

    def _make(*_args, **_kwargs):
        async def _backend(query, sectors=None):
            name = query.split(" (")[0]
            return [
                {
                    "id": i,
                    "content_preview": f"historical {name}",
                    "sector": "logistics",
                    "budget_id": f"BUD-{name[:3].upper()}-{i}",
                    "estimated_hours": float(hours),
                    "distance": 0.1 + 0.05 * i,
                }
                for i, hours in enumerate(hours_by_component.get(name, []))
            ]

        return _backend

    return _make


def fake_consensus(neighbors):
    """Deterministic stand-in for ``distance_weighted_consensus``."""
    if not neighbors:
        return 0, 0.0, 0.0
    return int(mean(h for h, _ in neighbors)), 0.85, 0.1


def wire(monkeypatch, *, wrapper, hours_by_component=None):
    """Install every double at the seams the production modules import from."""
    monkeypatch.setattr("app.dependencies.get_llm_wrapper", lambda: wrapper)
    monkeypatch.setattr(
        "app.domain.graph.supervisor.agents.make_retrieval_backend",
        backend_factory(hours_by_component or {}),
    )
    monkeypatch.setattr(
        "app.domain.graph.supervisor.agents.distance_weighted_consensus", fake_consensus
    )


@pytest.fixture
def wrapper() -> FakeWrapper:
    return FakeWrapper()
