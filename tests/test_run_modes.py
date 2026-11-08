import math
import random
from pathlib import Path

import pytest
from rich.console import Console

from agentic_larp import GrammarError, LarpError, main
from agentic_larp.packs import load_scenario, pick_scenario
from agentic_larp.sim import RunMode, Sim, SwarmSettings, Todo
from agentic_larp.stages import FLOW, PlanStage, Session, WorkStage, run_flow
from support import FakeClock, ScriptedKeys, output

DT = 0.05


def make_sim(
    *,
    length: float = 20.0,
    mode: RunMode = RunMode.CONVERGE,
    agents: int = 8,
    activity: float = 1.0,
    seed: int = 5,
) -> Sim:
    settings = SwarmSettings(
        agents=agents, interns=0, length=length, mode=mode, activity=activity
    )
    return Sim([pick_scenario(None, "prod")], settings, random.Random(seed))


def finish_times(sim: Sim, limit: float) -> dict[str, float]:
    """Tick until every agent is done or ``limit`` sim seconds pass."""
    done: dict[str, float] = {}
    while sim.now < limit and len(done) < len(sim.agents):
        sim.tick(DT)
        for agent in sim.agents:
            if agent.is_done and agent.name not in done:
                done[agent.name] = sim.now
    return done


def test_converge_is_the_default_with_a_twenty_second_length() -> None:
    settings = SwarmSettings()
    assert settings.mode is RunMode.CONVERGE
    assert settings.length == 20.0


def test_the_flow_starts_with_a_plan() -> None:
    assert FLOW == ("plan", "work", "wrap", "ready", "ship", "launch", "receipt")


def test_every_agent_gets_three_to_six_todos() -> None:
    sim = make_sim(agents=12)
    for agent in sim.agents:
        assert 3 <= len(agent.todos) <= 6
        assert agent.todos_done == 0
        assert all(todo.seconds > 0 for todo in agent.todos)
        assert all(todo.text.strip() for todo in agent.todos)


@pytest.mark.parametrize("length", [1.0, 5.0, 20.0, 60.0])
@pytest.mark.parametrize("key", ["prod", "girlfriend", "hacker"])
@pytest.mark.parametrize("seed", range(4))
def test_agents_converge_within_the_length_without_input(
    length: float, key: str, seed: int
) -> None:
    settings = SwarmSettings(agents=8, interns=16, length=length)
    sim = Sim([pick_scenario(None, key)], settings, random.Random(seed))
    done = finish_times(sim, 1.5 * length)
    assert set(done) == {agent.name for agent in sim.agents}
    assert min(done.values()) >= 0.5 * length
    assert sim.is_all_done
    assert sim.is_converged


def test_interns_stop_when_the_swarm_converges() -> None:
    settings = SwarmSettings(agents=4, interns=12, length=5.0)
    sim = Sim([pick_scenario(None, "prod")], settings, random.Random(3))
    finish_times(sim, 10.0)
    assert sim.is_converged
    assert all(intern.is_done for intern in sim.interns)


def test_agents_do_not_all_finish_at_once() -> None:
    done = finish_times(make_sim(length=20.0), 30.0)
    assert len(set(done.values())) > 1
    assert max(done.values()) - min(done.values()) >= 1.0


def test_a_faster_swarm_converges_sooner() -> None:
    slow = finish_times(make_sim(activity=1.0), 30.0)
    fast = finish_times(make_sim(activity=4.0), 30.0)
    assert max(fast.values()) < max(slow.values())


def test_todo_progress_only_moves_forward() -> None:
    sim = make_sim(length=10.0)
    previous = {agent.name: 0 for agent in sim.agents}
    for _ in range(int(15 / DT)):
        sim.tick(DT)
        for agent in sim.agents:
            assert previous[agent.name] <= agent.todos_done <= len(agent.todos)
            previous[agent.name] = agent.todos_done
    assert all(agent.todos_done == len(agent.todos) for agent in sim.agents)


def test_ship_it_rushes_without_converging() -> None:
    sim = make_sim(length=60.0)
    for _ in range(int(3 / DT)):
        sim.tick(DT)
    sim.ship()
    for _ in range(int(6 / DT)):
        sim.tick(DT)
    assert sim.is_all_done
    assert not sim.is_converged


def test_endless_runs_forever_with_scope_creep() -> None:
    sim = make_sim(length=5.0, mode=RunMode.ENDLESS)
    starting = {agent.name: len(agent.todos) for agent in sim.agents}
    for _ in range(int(600 / DT)):
        sim.tick(DT)
    assert not any(agent.is_done for agent in sim.agents)
    assert not sim.is_converged
    assert any(len(agent.todos) > starting[agent.name] for agent in sim.agents)
    assert any("scope creep" in text for _, text in sim.reports)


def test_scope_creep_todos_stay_as_big_as_the_original_ones() -> None:
    sim = make_sim(length=20.0, mode=RunMode.ENDLESS)
    original = {
        agent.name: sum(todo.seconds for todo in agent.todos) / len(agent.todos)
        for agent in sim.agents
    }
    starting = {agent.name: len(agent.todos) for agent in sim.agents}
    for _ in range(int(900 / DT)):
        sim.tick(DT)
    for agent in sim.agents:
        added = agent.todos[starting[agent.name] :]
        assert added
        assert all(todo.seconds >= 0.5 * original[agent.name] for todo in added)


def test_a_spawned_agent_brings_its_own_todos() -> None:
    sim = make_sim(length=10.0)
    for _ in range(int(2 / DT)):
        sim.tick(DT)
    newcomer = sim.spawn_agent()
    assert 3 <= len(newcomer.todos) <= 6
    assert finish_times(sim, 2 + 1.5 * 10.0).keys() >= {newcomer.name}


@pytest.mark.parametrize("length", [0.0, -1.0, math.nan, math.inf])
def test_sim_rejects_an_unusable_length(length: float) -> None:
    with pytest.raises(LarpError, match="length"):
        make_sim(length=length)


@pytest.mark.parametrize("seconds", [0.0, -3.0, math.nan, math.inf])
def test_a_todo_needs_a_positive_amount_of_work(seconds: float) -> None:
    with pytest.raises(LarpError, match="seconds"):
        Todo("write the tests", seconds)


def test_a_todo_needs_text() -> None:
    with pytest.raises(LarpError, match="text"):
        Todo("   ", 3.0)


def test_a_pack_can_write_its_own_todos(tmp_path: Path) -> None:
    path = tmp_path / "todo.toml"
    path.write_text(
        '[pack]\nkey = "todo"\ntask = "t"\n[areas]\nlobby = ["lobby.py"]\n'
        '[rules]\ntodo = ["Polish the #area#"]\n',
        encoding="utf-8",
    )
    sim = Sim([load_scenario(path)], SwarmSettings(agents=3), random.Random(1))
    for agent in sim.agents:
        assert {todo.text for todo in agent.todos} == {"Polish the lobby"}


def test_a_broken_todo_rule_fails_the_pack_check(tmp_path: Path) -> None:
    path = tmp_path / "bad.toml"
    path.write_text(
        '[pack]\nkey = "bad"\ntask = "t"\n[areas]\nx = ["x.py"]\n'
        '[rules]\ntodo = ["#nonsense_symbol#"]\n',
        encoding="utf-8",
    )
    with pytest.raises(GrammarError, match="nonsense_symbol"):
        load_scenario(path)


def make_session(
    console: Console, sim: Sim, *, keys: ScriptedKeys, auto: float | None = None
) -> Session:
    return Session(
        console=console,
        task=sim.task,
        sim=sim,
        rng=random.Random(2),
        keys=keys,
        auto=auto,
    )


def screen_text(console: Console, stage: PlanStage | WorkStage) -> str:
    with console.capture() as capture:
        console.print(stage.render(), height=console.height)
    return capture.get()


def test_the_plan_lists_every_agents_todos(console: Console, clock: FakeClock) -> None:
    sim = make_sim(agents=2)
    session = make_session(console, sim, keys=ScriptedKeys(clock))
    plan = PlanStage()
    plan.begin(session)
    text = screen_text(console, plan)
    assert "TodoWrite" in text
    for agent in sim.agents:
        assert agent.name in text
        for todo in agent.todos:
            assert todo.text in text


def test_the_plan_moves_on_by_itself(console: Console, clock: FakeClock) -> None:
    sim = make_sim()
    plan = PlanStage()
    plan.begin(make_session(console, sim, keys=ScriptedKeys(clock)))
    for _ in range(int(1 / DT)):
        plan.tick(DT)
    assert not plan.is_done
    for _ in range(int(2 / DT)):
        plan.tick(DT)
    assert plan.is_done
    assert plan.next_stage is None


def test_any_key_skips_the_plan_and_no_work_happens_during_it(
    console: Console, clock: FakeClock
) -> None:
    sim = make_sim()
    calls = sim.total_calls
    plan = PlanStage()
    plan.begin(make_session(console, sim, keys=ScriptedKeys(clock)))
    plan.tick(DT)
    plan.on_key("x")
    assert plan.is_done
    assert sim.total_calls == calls
    assert all(agent.todos_done == 0 for agent in sim.agents)


def test_panels_show_todo_progress(console: Console, clock: FakeClock) -> None:
    sim = make_sim(agents=2, length=10.0)
    work = WorkStage()
    work.begin(make_session(console, sim, keys=ScriptedKeys(clock)))
    for _ in range(int(6 / DT)):
        work.tick(DT)
    lines = screen_text(console, work).splitlines()
    for agent in sim.agents:
        progress = f"{agent.todos_done}/{len(agent.todos)}"
        assert any(agent.name in line and progress in line for line in lines)


def test_a_converged_run_skips_wrap_and_waits_for_one_ship_it(
    console: Console, clock: FakeClock
) -> None:
    settings = SwarmSettings(agents=4, interns=0, length=10.0)
    sim = Sim([pick_scenario(None, "startup")], settings, random.Random(5))
    keys = ScriptedKeys(clock, [*((40.0, key) for key in "ship it"), (40.0, "enter")])
    session = make_session(console, sim, keys=keys)
    assert run_flow(session) == 0
    reports = [text for _, text in sim.reports]
    assert sim.is_converged
    assert "all 4 agents done. ready to ship." in reports
    assert not any("wrapping up" in text for text in reports)
    assert "✓ shipped" in output(console)
    assert 40.0 <= clock.now < 50.0


def test_cli_length_makes_the_run_converge_early(
    capsys: pytest.CaptureFixture[str], clock: FakeClock
) -> None:
    # Non-interactive runs auto-ship 6 s into the work. A 1 s length converges first
    # and ships about 9 s in; the default length would still be wrapping up then.
    args = ["-s", "startup", "--app", "none", "-i", "0", "--seed", "1"]
    assert main([*args, "--length", "1"]) == 0
    assert "✓ shipped" in capsys.readouterr().out
    assert clock.now < 11.0


def test_cli_forever_never_converges(
    capsys: pytest.CaptureFixture[str], clock: FakeClock
) -> None:
    # Without --forever a 1 s length converges in about 9 s; endless runs wait for
    # the 4 s auto-ship and a wrap-up, so they take at least 12 s.
    args = ["-s", "prod", "--app", "none", "-i", "0", "--seed", "1"]
    assert main([*args, "--length", "1", "--forever", "--auto", "4"]) == 0
    assert "✓ shipped" in capsys.readouterr().out
    assert clock.now > 11.5


@pytest.mark.parametrize("value", ["0", "-5", "nan", "inf", "soon"])
def test_cli_rejects_a_bad_length(
    capsys: pytest.CaptureFixture[str], value: str
) -> None:
    with pytest.raises(SystemExit, match="2"):
        main(["--length", value])
    assert "--length" in capsys.readouterr().err


def test_ship_it_typed_during_the_plan_reaches_the_work(
    console: Console, clock: FakeClock
) -> None:
    sim = make_sim(agents=3, length=60.0)
    burst = [(0.5, key) for key in [*"ship it", "enter"]]
    session = make_session(
        console, sim, keys=ScriptedKeys(clock, [*burst, (20.0, "enter")])
    )
    # Without the "ship it", a 60 s swarm would still be working when the enter at
    # 20 s arrives, and the run would never reach the ship stage.
    assert run_flow(session) == 0
    assert sim.is_all_done
    assert not sim.is_converged
    assert 20.0 <= clock.now < 25.0


@pytest.mark.parametrize(
    ("width", "height", "agents"), [(80, 24, 2), (120, 40, 9), (160, 50, 12)]
)
def test_the_plan_shows_every_agent_on_common_terminals(
    width: int, height: int, agents: int, clock: FakeClock
) -> None:
    small = Console(width=width, height=height, force_terminal=True, color_system=None)
    sim = make_sim(agents=agents)
    plan = PlanStage()
    plan.begin(make_session(small, sim, keys=ScriptedKeys(clock)))
    with small.capture() as capture:
        small.print(plan.render(), height=height)
    text = capture.get()
    assert len(text.splitlines()) <= height
    for agent in sim.agents:
        assert agent.name in text
