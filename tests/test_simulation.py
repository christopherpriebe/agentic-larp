import random

import pytest

from agentic_larp import LarpError
from agentic_larp.packs import pick_scenario
from agentic_larp.sim import (
    LogLine,
    RunMode,
    Sim,
    SwarmSettings,
    format_duration,
    format_tokens,
)


def make_sim(settings: SwarmSettings | None = None, seed: int = 7) -> Sim:
    return Sim(
        [pick_scenario(None, "girlfriend")],
        settings or SwarmSettings(),
        random.Random(seed),
    )


def run(sim: Sim, seconds: float, dt: float = 0.05) -> None:
    for _ in range(int(seconds / dt)):
        sim.tick(dt)


def test_sim_starts_mid_run_with_busy_agents() -> None:
    sim = make_sim(SwarmSettings(agents=3, interns=5))
    assert [agent.name for agent in sim.agents] == [
        "maestro-1",
        "maestro-2",
        "maestro-3",
    ]
    assert [agent.area for agent in sim.agents] == ["render", "voice", "heart"]
    assert all(agent.log for agent in sim.agents)
    assert len(sim.interns) == 5
    assert sim.run_time >= 4 * 60
    assert sim.running == 3
    assert not sim.is_all_done


def test_sim_is_reproducible_with_a_seed() -> None:
    first, second = make_sim(seed=11), make_sim(seed=11)
    run(first, 3)
    run(second, 3)
    assert [list(agent.log) for agent in first.agents] == [
        list(agent.log) for agent in second.agents
    ]


def test_ticking_streams_tool_calls_and_spends_money() -> None:
    sim = make_sim()
    calls, cost, started = sim.total_calls, sim.cost, sim.run_time
    run(sim, 10)
    kinds = {line.kind for agent in sim.agents for line in agent.log}
    assert {"tool", "result", "quip"} <= kinds
    assert sim.total_calls > calls
    assert sim.cost > cost
    assert sim.run_time > started


def test_custom_model_names_label_the_swarm() -> None:
    sim = make_sim(
        SwarmSettings(agents=1, interns=1, lead_model="fable", intern_model="sonnet")
    )
    assert sim.agents[0].name == "fable-1"
    assert sim.interns[0].name == "sonnet-01"


def test_poke_makes_agents_frantic_up_to_a_cap() -> None:
    sim = make_sim()
    for _ in range(100):
        sim.poke()
    assert sim.energy == 25.0


def test_mashing_keys_makes_more_progress() -> None:
    endless = SwarmSettings(mode=RunMode.ENDLESS)
    calm, frantic = make_sim(endless, seed=5), make_sim(endless, seed=5)
    for _ in range(200):
        frantic.poke(5)
        frantic.tick(0.05)
        calm.tick(0.05)
    assert frantic.total_calls > calm.total_calls
    assert frantic.run_time == pytest.approx(
        calm.run_time
    )  # mashing never speeds the clock


def test_broadcast_is_routed_and_answered() -> None:
    sim = make_sim(SwarmSettings(agents=2))
    sim.broadcast("add dark mode")
    assert ("you", "add dark mode") in sim.reports
    run(sim, 30)
    replies = [
        line.text
        for agent in sim.agents
        for line in agent.log
        if line.text.startswith("Re:")
    ]
    assert replies == ['Re: "add dark mode". On it.']


def test_spawn_agent_takes_the_next_area_and_reports_it() -> None:
    sim = make_sim(SwarmSettings(agents=8))
    agent = sim.spawn_agent()
    assert agent.name == "maestro-9"
    assert agent.area == "render"  # areas wrap around
    assert sim.elapsed(agent) == 0.0
    assert sim.reports[-1] == (sim.orchestrator, "spawning maestro-9 → render")


def test_ship_finishes_every_agent_and_freezes_their_clocks() -> None:
    sim = make_sim(SwarmSettings(agents=4))
    sim.ship()
    run(sim, 15)
    assert sim.is_all_done
    assert sim.running == 0
    assert all(intern.is_done for intern in sim.interns)
    for agent in sim.agents:
        assert agent.log[-1].kind == "done"
        assert agent.log[-1].text.startswith(f"✓ {agent.area} done")
        frozen = sim.elapsed(agent)
        run(sim, 1)
        assert sim.elapsed(agent) == frozen


def test_interns_cycle_between_tasks_while_running() -> None:
    sim = make_sim(SwarmSettings(interns=4))
    seen = set()
    for _ in range(400):
        sim.tick(0.05)
        seen |= {(intern.name, intern.is_done) for intern in sim.interns}
    assert {done for _, done in seen} == {True, False}


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(0, "0s"), (42.9, "42s"), (187, "3m 7s"), (4320, "1h 12m")],
)
def test_format_duration(seconds: float, expected: str) -> None:
    assert format_duration(seconds) == expected


@pytest.mark.parametrize(
    ("count", "expected"),
    [(950, "950"), (12_340, "12.3k"), (1_240_000, "1.24M")],
)
def test_format_tokens(count: float, expected: str) -> None:
    assert format_tokens(count) == expected


def test_log_lines_are_values() -> None:
    assert LogLine("tool", "x.py", "Read") == LogLine("tool", "x.py", "Read")


def test_clock_runs_at_real_time_even_when_frantic() -> None:
    sim = make_sim(SwarmSettings(mode=RunMode.ENDLESS))
    started = sim.run_time
    for _ in range(200):
        sim.poke(25)
        sim.tick(0.05)
    assert sim.run_time - started == pytest.approx(10.0)


def test_activity_speeds_up_the_agents_but_not_the_clock() -> None:
    slow = make_sim(SwarmSettings(activity=1.0, mode=RunMode.ENDLESS), seed=6)
    fast = make_sim(SwarmSettings(activity=4.0, mode=RunMode.ENDLESS), seed=6)
    slow_start, fast_start = slow.run_time, fast.run_time
    calls = slow.total_calls, fast.total_calls
    run(slow, 10)
    run(fast, 10)
    assert fast.total_calls - calls[1] > 2 * (slow.total_calls - calls[0])
    assert slow.run_time - slow_start == pytest.approx(10.0)
    assert fast.run_time - fast_start == pytest.approx(10.0)


def test_tokens_and_money_race_ahead_of_the_clock() -> None:
    sim = make_sim()
    tokens, cost = sim.total_tokens, sim.cost
    run(sim, 10)
    assert sim.total_tokens - tokens >= 200_000
    assert sim.cost - cost >= 5.0


def test_clock_keeps_running_while_agents_wrap_up() -> None:
    sim = make_sim()
    sim.ship()
    started = sim.run_time
    sim.tick(0.1)
    assert not sim.is_all_done
    assert sim.run_time - started == pytest.approx(0.1)


def test_everything_freezes_once_every_agent_is_done() -> None:
    sim = make_sim(SwarmSettings(agents=3))
    sim.ship()
    run(sim, 20)
    assert sim.is_all_done
    snapshot = (sim.run_time, sim.total_calls, sim.total_tokens, sim.cost)
    for _ in range(200):
        sim.poke(25)
        sim.tick(0.05)
    assert (sim.run_time, sim.total_calls, sim.total_tokens, sim.cost) == snapshot


@pytest.mark.parametrize("activity", [0.0, -1.0, float("nan"), float("inf")])
def test_sim_rejects_unusable_activity(activity: float) -> None:
    with pytest.raises(LarpError, match="activity must be a finite number above 0"):
        make_sim(SwarmSettings(activity=activity))


def test_sim_rejects_an_empty_swarm() -> None:
    with pytest.raises(LarpError, match="at least one agent"):
        make_sim(SwarmSettings(agents=0))


def test_tokens_still_climb_at_a_crawl() -> None:
    sim = make_sim(SwarmSettings(activity=0.04))
    tokens = sim.total_tokens
    for _ in range(2000):
        sim.tick(0.005)
    assert sim.total_tokens - tokens >= 5_000


def test_sim_needs_at_least_one_pack() -> None:
    with pytest.raises(LarpError, match="at least one pack"):
        Sim([], SwarmSettings(), random.Random(1))


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"interns": -1}, "interns"),
        ({"agents": 0}, "at least one agent"),
        ({"activity": 0.0}, "activity"),
        ({"length": float("nan")}, "length"),
    ],
)
def test_swarm_settings_reject_bad_values_when_built(
    changes: dict[str, float], message: str
) -> None:
    with pytest.raises(LarpError, match=message):
        SwarmSettings(**changes)  # ty: ignore[invalid-argument-type] - parametrized kwargs of mixed types
