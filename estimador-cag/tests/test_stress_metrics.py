import pytest

from evals.stress.metrics import CostBudgetMetric, LatencyBudgetMetric, MemoryDriftMetric


def test_latency_budget_passes():
    result = LatencyBudgetMetric(budget_ms=1000).evaluate({"latency_ms": 999})
    assert result.passed is True
    assert result.score == 1.0


def test_latency_budget_fails():
    result = LatencyBudgetMetric(budget_ms=1000).evaluate({"latency_ms": 1001})
    assert result.passed is False
    assert result.score == 0.0


def test_latency_budget_boundary_equals_budget_passes():
    result = LatencyBudgetMetric(budget_ms=1000).evaluate({"latency_ms": 1000})
    assert result.passed is True


def test_cost_budget_passes():
    result = CostBudgetMetric(budget_usd=0.01).evaluate({"cost_usd": 0.009})
    assert result.passed is True
    assert result.score == 1.0


def test_cost_budget_fails():
    result = CostBudgetMetric(budget_usd=0.01).evaluate({"cost_usd": 0.011})
    assert result.passed is False
    assert result.score == 0.0


def test_memory_drift_finds_fact_in_metadata():
    snapshot = {"project_metadata": {"project_name": "Nimbus Portal"}}
    result = MemoryDriftMetric("Nimbus Portal").evaluate(snapshot)
    assert result.passed is True
    assert result.details["matched_fields"] == ["metadata"]


def test_memory_drift_finds_fact_in_summary():
    snapshot = {"summary": "The budget locked: 30000 EUR fact is preserved."}
    result = MemoryDriftMetric("budget locked: 30000 EUR", where=["summary"]).evaluate(snapshot)
    assert result.passed is True


def test_memory_drift_fails_when_absent():
    snapshot = {"summary": "No matching facts here.", "project_metadata": {}}
    result = MemoryDriftMetric("project name: Nimbus").evaluate(snapshot)
    assert result.passed is False
    assert result.score == 0.0


def test_memory_drift_is_case_insensitive():
    snapshot = {"anchors": ["STACK INCLUDES FLUTTER"]}
    result = MemoryDriftMetric("stack includes flutter", where=["anchors"]).evaluate(snapshot)
    assert result.passed is True


def test_memory_drift_rejects_unknown_fields():
    with pytest.raises(ValueError):
        MemoryDriftMetric("anything", where=["database"])
