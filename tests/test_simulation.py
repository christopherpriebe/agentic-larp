import random

import pytest

from agentic_larp import (
    LogLine,
    Sim,
    SwarmSettings,
    format_duration,
    format_tokens,
    pick_scenario,
)


def make_sim(settings: SwarmSettings | None = None, seed: int = 7) -> Sim:
    return Sim(
        pick_scenario(None, "girlfriend"),
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
    assert sim.fake >= 4 * 60
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
    calls, cost, fake = sim.total_calls, sim.cost, sim.fake
    run(sim, 10)
    kinds = {line.kind for agent in sim.agents for line in agent.log}
    assert {"tool", "result", "quip"} <= kinds
    assert sim.total_calls > calls
    assert sim.cost > cost
    assert sim.fake > fake


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
    calm, frantic = make_sim(seed=5), make_sim(seed=5)
    for _ in range(200):
        frantic.poke(5)
        frantic.tick(0.05)
        calm.tick(0.05)
    assert frantic.total_calls > calm.total_calls
    assert frantic.fake > calm.fake


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
