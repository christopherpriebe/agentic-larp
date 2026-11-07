import importlib.metadata
import itertools
import random
from collections import Counter, deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import pytest

from agentic_larp import (
    POLICY_ENTRY_POINT_GROUP,
    ChoicePolicy,
    Grammar,
    GrammarError,
    RandomPolicy,
    Sim,
    SwarmSettings,
    VariedPolicy,
    load_scenario,
    main,
    pick_scenario,
    policy_registry,
)
from support import FakeClock

THREE = (("a", 1.0), ("b", 1.0), ("c", 1.0))


def picks(
    policy: ChoicePolicy,
    symbol: str,
    alternatives: tuple[tuple[str, float], ...],
    count: int,
    seed: int = 0,
) -> list[int]:
    rng = random.Random(seed)
    return [policy.choose(symbol, alternatives, rng) for _ in range(count)]


def test_random_policy_matches_a_plain_weighted_draw() -> None:
    alternatives = (("a", 5.0), ("b", 1.0), ("c", 2.5))
    expected_rng, policy_rng = random.Random(7), random.Random(7)
    policy = RandomPolicy()
    for _ in range(500):
        expected = expected_rng.choices(range(3), [w for _, w in alternatives])[0]
        assert policy.choose("x", alternatives, policy_rng) == expected


def test_expand_defaults_to_random_policy() -> None:
    grammar = Grammar.from_mapping(
        {"line": "#word# #word# #word#", "word": ["a", "b", "c", "d"]}
    )
    for seed in range(20):
        assert grammar.expand("line", random.Random(seed)) == grammar.expand(
            "line", random.Random(seed), policy=RandomPolicy()
        )


def test_varied_policy_never_repeats_its_last_pick() -> None:
    sequence = picks(VariedPolicy(), "code", THREE, 3000)
    assert all(a != b for a, b in itertools.pairwise(sequence))
    assert set(sequence) == {0, 1, 2}


def test_varied_policy_with_one_alternative_still_picks_it() -> None:
    assert picks(VariedPolicy(), "only", (("x", 1.0),), 50) == [0] * 50


def test_varied_policy_still_follows_weights() -> None:
    sequence = picks(
        VariedPolicy(), "w", (("heavy", 8.0), ("b", 1.0), ("c", 1.0)), 6000
    )
    counts = Counter(sequence)
    assert counts[0] > counts[1]
    assert counts[0] > counts[2]


def test_varied_policy_also_shies_away_from_older_picks() -> None:
    alternatives = tuple((name, 1.0) for name in "abcd")
    sequence = picks(VariedPolicy(), "s", alternatives, 6000)
    gap_two_repeats = sum(a == c for a, c in zip(sequence, sequence[2:], strict=False))
    # Excluding only the last pick, a uniform draw repeats two back a third of the time.
    assert gap_two_repeats / (len(sequence) - 2) < 0.25


def test_varied_policy_remembers_each_symbol_separately() -> None:
    policy = VariedPolicy()
    rng = random.Random(3)
    two = (("x", 1.0), ("y", 1.0))
    first, second = [], []
    for _ in range(200):
        first.append(policy.choose("first", two, rng))
        second.append(policy.choose("second", two, rng))
    for sequence in (first, second):
        assert all(a != b for a, b in itertools.pairwise(sequence))


@pytest.mark.parametrize(
    ("make", "message"),
    [
        pytest.param(lambda: VariedPolicy(memory=0), "memory", id="memory-zero"),
        pytest.param(
            lambda: VariedPolicy(penalty=-0.1), "penalty", id="penalty-negative"
        ),
        pytest.param(
            lambda: VariedPolicy(penalty=1.5), "penalty", id="penalty-above-one"
        ),
    ],
)
def test_varied_policy_rejects_bad_settings(
    make: Callable[[], ChoicePolicy], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        make()


def test_varied_expansion_avoids_back_to_back_lines() -> None:
    grammar = Grammar.from_mapping({"code": ["a = 1;", "b = 2;", "c = 3;"]})
    policy, rng = VariedPolicy(), random.Random(5)
    lines = [grammar.expand("code", rng, policy=policy) for _ in range(500)]
    assert all(a != b for a, b in itertools.pairwise(lines))


TINY_PACK = """
[pack]
key = "tiny"
task = "write three lines"

[areas]
core = ["core.py"]

[rules]
code = ["a = 1", "b = 2", "c = 3"]
"""


def streamed_repeats(policy: Callable[[], ChoicePolicy], directory: Path) -> int:
    """Count back-to-back identical diff lines across everything the agents wrote.

    The pack has three code lines, so a plain random draw repeats often.
    """
    path = directory / "tiny.toml"
    path.write_text(TINY_PACK, encoding="utf-8")
    settings = SwarmSettings(agents=8, interns=0, policy=policy)
    sim = Sim([load_scenario(path)], settings, random.Random(12))
    for agent in sim.agents:
        # Uncapped, so the log keeps every line the agent writes.
        agent.log = deque(agent.log)
    for _ in range(4000):
        sim.tick(0.05)
    return sum(
        a.kind == b.kind == "diff" and a.text == b.text
        for agent in sim.agents
        for a, b in itertools.pairwise(agent.log)
    )


def test_random_agents_sometimes_repeat_a_diff_line(tmp_path: Path) -> None:
    assert streamed_repeats(RandomPolicy, tmp_path) > 0


def test_varied_agents_never_repeat_a_diff_line(tmp_path: Path) -> None:
    assert streamed_repeats(VariedPolicy, tmp_path) == 0


def test_every_agent_and_intern_gets_its_own_policy() -> None:
    made: list[ChoicePolicy] = []

    def factory() -> ChoicePolicy:
        policy = VariedPolicy()
        made.append(policy)
        return policy

    sim = Sim(
        [pick_scenario(None, "prod")],
        SwarmSettings(agents=3, interns=2, policy=factory),
        random.Random(0),
    )
    assert len(made) == 5
    assert len({id(policy) for policy in made}) == 5
    sim.spawn_agent()
    assert len(made) == 6


def test_swarm_defaults_to_random_policy() -> None:
    assert SwarmSettings().policy is RandomPolicy


def test_registry_has_the_builtins() -> None:
    registry = policy_registry()
    assert registry["random"] is RandomPolicy
    assert registry["varied"] is VariedPolicy


@dataclass
class FakeEntryPoint:
    name: str
    target: object

    def load(self) -> object:
        return self.target


class FirstChoice:
    def __init__(self) -> None:
        self.calls = 0

    def choose(
        self,
        _symbol: str,
        alternatives: Sequence[tuple[str, float]],
        _rng: random.Random,
    ) -> int:
        self.calls += 1
        return len(alternatives) - 1


def test_registry_includes_plugin_policies(monkeypatch: pytest.MonkeyPatch) -> None:
    real = importlib.metadata.entry_points

    def fake_entry_points(*, group: str) -> object:
        if group == POLICY_ENTRY_POINT_GROUP:
            return [FakeEntryPoint("first-only", FirstChoice)]
        return real(group=group)

    monkeypatch.setattr(importlib.metadata, "entry_points", fake_entry_points)
    assert policy_registry()["first-only"] is FirstChoice


def test_cli_policy_flag_runs_and_lists(
    capsys: pytest.CaptureFixture[str], clock: FakeClock
) -> None:
    assert main(["--list"]) == 0
    listing = capsys.readouterr().out
    assert "random" in listing
    assert "varied" in listing
    assert (
        main(
            [
                "-s",
                "prod",
                "--policy",
                "varied",
                "--auto",
                "1",
                "--speed",
                "4",
                "--app",
                "none",
            ]
        )
        == 0
    )
    assert "✓ shipped" in capsys.readouterr().out
    assert clock.now > 1.0


def test_cli_rejects_an_unknown_policy(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit, match="2"):
        main(["--policy", "chaos"])
    assert "--policy" in capsys.readouterr().err


def test_one_varied_policy_can_serve_grammars_that_share_a_symbol() -> None:
    wide = Grammar.from_mapping({"code": ["a", "b", "c", "d"]})
    narrow = Grammar.from_mapping({"code": ["x", "y"]})
    policy, rng = VariedPolicy(), random.Random(4)
    wide_lines, narrow_lines = [], []
    for _ in range(300):
        wide_lines.append(wide.expand("code", rng, policy=policy))
        narrow_lines.append(narrow.expand("code", rng, policy=policy))
    for lines in (wide_lines, narrow_lines):
        assert all(a != b for a, b in itertools.pairwise(lines))


def test_varied_policy_survives_zero_weight_alternatives() -> None:
    grammar = Grammar({"r": (("only", 1.0), ("never", 0.0))})
    policy, rng = VariedPolicy(), random.Random(0)
    assert {grammar.expand("r", rng, policy=policy) for _ in range(50)} == {"only"}


class OffTheEnd:
    def choose(
        self,
        _symbol: str,
        alternatives: Sequence[tuple[str, float]],
        _rng: random.Random,
    ) -> int:
        return len(alternatives)


def test_a_policy_returning_a_bad_index_is_a_grammar_error() -> None:
    grammar = Grammar.from_mapping({"code": ["a", "b"]})
    with pytest.raises(GrammarError, match="policy"):
        grammar.expand("code", random.Random(0), policy=OffTheEnd())


def test_registered_plugin_policy_drives_expansion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real = importlib.metadata.entry_points

    def fake_entry_points(*, group: str) -> object:
        if group == POLICY_ENTRY_POINT_GROUP:
            return [FakeEntryPoint("last-one", FirstChoice)]
        return real(group=group)

    monkeypatch.setattr(importlib.metadata, "entry_points", fake_entry_points)
    policy = policy_registry()["last-one"]()
    grammar = Grammar.from_mapping({"code": ["a = 1;", "b = 2;", "c = 3;"]})
    assert grammar.expand("code", random.Random(0), policy=policy) == "c = 3;"


@dataclass
class BrokenEntryPoint:
    name: str

    def load(self) -> object:
        message = "plugin is broken"
        raise ImportError(message)


def plugin_points(monkeypatch: pytest.MonkeyPatch, *points: object) -> None:
    real = importlib.metadata.entry_points

    def fake_entry_points(*, group: str) -> object:
        if group == POLICY_ENTRY_POINT_GROUP:
            return list(points)
        return real(group=group)

    monkeypatch.setattr(importlib.metadata, "entry_points", fake_entry_points)


def test_a_plugin_that_fails_to_load_only_warns(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    plugin_points(monkeypatch, BrokenEntryPoint("broken"))
    assert main(["--list"]) == 0
    text = capsys.readouterr().out
    assert "warning" in text
    assert "broken" in text
    assert "varied" in text


def test_choosing_a_plugin_that_is_not_a_policy_is_a_usage_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    plugin_points(monkeypatch, FakeEntryPoint("bogus", "not a factory"))
    with pytest.raises(SystemExit, match="2"):
        main(["--policy", "bogus"])
    assert "--policy" in capsys.readouterr().err
