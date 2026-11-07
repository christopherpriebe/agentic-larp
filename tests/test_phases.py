import itertools
import random
from collections import Counter

import pytest

from agentic_larp import (
    PHASES,
    SCENARIOS,
    TOOLCHAINS,
    PhasedPolicy,
    SwarmSettings,
    main,
    policy_registry,
)
from support import FakeClock

# Which phase may follow which (ignoring "anytime" picks in between).
ALLOWED = {
    "explore": {"explore", "implement"},
    "implement": {"implement", "build", "test"},
    "build": {"test", "debug", "implement"},
    "test": {"implement", "debug", "explore", "test"},
    "debug": {"test", "build", "implement"},
}
ACTION = tuple((f"#{phase}#", 1.0) for phase in (*PHASES, "anytime"))


def phase_sequence(count: int, seed: int = 0) -> list[str]:
    policy, rng = PhasedPolicy(), random.Random(seed)
    return [
        ACTION[policy.choose("action", ACTION, rng)][0].strip("#") for _ in range(count)
    ]


def test_phases_are_the_five_work_phases() -> None:
    assert PHASES == ("explore", "implement", "build", "test", "debug")


def test_phased_policy_follows_a_realistic_rhythm() -> None:
    sequence = [phase for phase in phase_sequence(4000) if phase != "anytime"]
    for before, after in itertools.pairwise(sequence):
        assert after in ALLOWED[before], (before, after)
    assert set(sequence) == set(PHASES)


def test_anytime_actions_are_sprinkled_in() -> None:
    counts = Counter(phase_sequence(4000))
    share = counts["anytime"] / 4000
    assert 0.05 <= share <= 0.35


def test_implementation_dominates_like_real_work() -> None:
    counts = Counter(phase_sequence(4000))
    assert counts["implement"] == max(counts[phase] for phase in PHASES)


def test_phased_policy_is_varied_for_other_rules() -> None:
    policy, rng = PhasedPolicy(), random.Random(1)
    code = (("a", 1.0), ("b", 1.0), ("c", 1.0))
    picks = [policy.choose("code", code, rng) for _ in range(500)]
    assert all(a != b for a, b in itertools.pairwise(picks))


def test_phased_policy_copes_with_an_action_rule_without_phases() -> None:
    policy, rng = PhasedPolicy(), random.Random(2)
    plain = (("#edit#", 3.0), ("#bash#", 1.0))
    picks = [policy.choose("action", plain, rng) for _ in range(200)]
    assert set(picks) == {0, 1}


def test_every_toolchain_and_pack_defines_the_phases() -> None:
    for pack in (*TOOLCHAINS.values(), *SCENARIOS.values()):
        for rule in (*PHASES, "anytime"):
            assert rule in pack.grammar.rules, (pack.key, rule)


def test_registry_has_phased() -> None:
    assert policy_registry()["phased"] is PhasedPolicy


def test_phased_runs_end_to_end(
    capsys: pytest.CaptureFixture[str], clock: FakeClock
) -> None:
    args = [
        "-s",
        "girlfriend",
        "--policy",
        "phased",
        "--auto",
        "1",
        "--speed",
        "4",
        "--app",
        "none",
    ]
    assert main(args) == 0
    assert "✓ shipped" in capsys.readouterr().out
    assert clock.now > 1.0


def test_swarm_settings_accept_phased() -> None:
    assert SwarmSettings(policy=PhasedPolicy).policy is PhasedPolicy
