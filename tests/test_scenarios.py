import random

import pytest

from agentic_larp.packs import (
    BOUND_SYMBOLS,
    REQUIRED_SYMBOLS,
    SCENARIOS,
    generic_scenario,
    pick_scenario,
    task_words,
)


@pytest.mark.parametrize(
    ("task", "key"),
    [
        ("build me a girlfriend", "girlfriend"),
        ("I'm so single", "girlfriend"),
        ("make a unicorn startup", "startup"),
        ("hack the pentagon mainframe", "hacker"),
        ("deploy on friday", "prod"),
        ("uber for cats", "generic"),
    ],
)
def test_pick_scenario_matches_task_keywords(task: str, key: str) -> None:
    scenario = pick_scenario(task, rng=random.Random(0))
    assert scenario.key == key
    assert scenario.task == task


def test_pick_scenario_by_key_keeps_the_given_task() -> None:
    scenario = pick_scenario("my side project", "hacker")
    assert scenario.key == "hacker"
    assert scenario.task == "my side project"
    assert scenario.app == "hacker"


def test_pick_scenario_by_key_without_task_uses_the_default_task() -> None:
    assert pick_scenario(None, "prod").task == "ship to prod on a friday"


def test_pick_scenario_forced_generic_has_a_fallback_task() -> None:
    assert pick_scenario(None, "generic").task == "build the thing"


def test_pick_scenario_without_task_is_a_builtin() -> None:
    assert pick_scenario(None, rng=random.Random(3)) in SCENARIOS.values()


def test_task_words_drops_filler_and_duplicates() -> None:
    assert task_words("Build an app for CATS and cats, with uber") == ["cats", "uber"]


def test_generic_scenario_turns_task_words_into_areas() -> None:
    scenario = generic_scenario("uber for cats", random.Random(1))
    assert list(scenario.areas)[:2] == ["uber", "cats"]
    assert len(scenario.areas) == 8
    assert scenario.areas["cats"] == ("cats.ts", "Cats.tsx", "cats.test.ts")
    rng = random.Random(2)
    quips = {scenario.grammar.expand("quip", rng) for _ in range(500)}
    assert "Cats is done." in quips
    assert scenario.app in {"deploy", "stonks"}


def test_generic_scenario_is_a_complete_pack() -> None:
    scenario = generic_scenario("uber for cats", random.Random(1))
    for area in scenario.areas:
        scenario.grammar_for(area).check(required=REQUIRED_SYMBOLS, bound=BOUND_SYMBOLS)


def test_every_builtin_scenario_is_complete() -> None:
    for key, scenario in SCENARIOS.items():
        assert scenario.key == key
        assert len(scenario.areas) == 8
        assert all(scenario.areas.values())
        assert scenario.keywords
