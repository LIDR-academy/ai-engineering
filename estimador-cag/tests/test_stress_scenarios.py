from evals.stress.scenarios import SCENARIOS


def test_all_required_scenarios_exist():
    assert set(SCENARIOS) == {"growing", "pivot", "contradiction"}


def test_each_scenario_has_at_least_twenty_turns():
    for scenario in SCENARIOS.values():
        assert len(scenario.turns) >= 20


def test_each_fact_to_remember_is_non_empty():
    for scenario in SCENARIOS.values():
        for turn in scenario.turns:
            assert turn.fact_to_remember.strip()


def test_scenario_names_are_unique():
    names = [scenario.name for scenario in SCENARIOS.values()]
    assert len(names) == len(set(names))
