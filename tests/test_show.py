import random
from typing import TypeVar

import pytest
from rich.console import Console

from agentic_larp import (
    LogLine,
    ReadyStage,
    ScreenStage,
    Session,
    ShipStage,
    Sim,
    SwarmSettings,
    Wall,
    WorkStage,
    WrapStage,
    pick_scenario,
    render_entry,
)


def make_sim() -> Sim:
    return Sim([pick_scenario(None, "prod")], SwarmSettings(agents=6), random.Random(4))


def make_wall(console: Console) -> Wall:
    return Wall(make_sim(), console)


def make_session(console: Console, *, app: str = "none") -> tuple[Session, Sim]:
    sim = make_sim()
    session = Session(
        console=console, task=sim.task, sim=sim, rng=random.Random(4), app=app
    )
    return session, sim


S = TypeVar("S", bound=ScreenStage)


def start(stage: S, session: Session) -> S:
    stage.begin(session)
    return stage


def screen_text(console: Console, screen: Wall | ScreenStage) -> str:
    with console.capture() as capture:
        console.print(screen.render(), height=console.height)
    return capture.get()


def type_line(stage: ScreenStage, text: str) -> None:
    for key in text:
        stage.on_key(key)
    stage.on_key("enter")


def advance(screen: Wall | ScreenStage, seconds: float, dt: float = 0.05) -> None:
    for _ in range(int(seconds / dt)):
        if isinstance(screen, Wall):
            screen.step(dt)
        else:
            screen.tick(dt)


@pytest.mark.parametrize(
    "entry",
    [
        LogLine("tool", "migrations/0042.sql", "Edit"),
        LogLine("diff", "retries = 64", "-", 16),
        LogLine("diff", "retries = 128", "+", 171),
        LogLine("result", "✓ 4 passed", "green"),
        LogLine("quip", "Paged nobody."),
        LogLine("done", "✓ db done · 40 calls"),
        LogLine("quip", "x" * 200),
    ],
)
def test_render_entry_fills_exactly_one_line(entry: LogLine) -> None:
    line = render_entry(entry, 30)
    assert line.cell_len == 30
    assert "\n" not in line.plain


def test_render_entry_formats_tool_calls_and_diffs() -> None:
    assert (
        render_entry(LogLine("tool", "tts.cpp", "Edit"), 20).plain.rstrip()
        == "● Edit(tts.cpp)"
    )
    assert (
        render_entry(LogLine("diff", "rate = 165;", "+", 171), 20).plain.rstrip()
        == "171 + rate = 165;"
    )


def test_screen_shows_every_agent_the_swarm_and_the_prompt(console: Console) -> None:
    wall = make_wall(console)
    advance(wall, 2)
    text = screen_text(console, wall)
    for agent in wall.sim.agents:
        assert agent.name in text
    assert "intern-01" in text
    assert "orchestrating 6" in text
    assert "'ship it' to ship" in text


def test_tiny_terminal_hides_the_swarm() -> None:
    small = Console(width=80, height=20, force_terminal=True, color_system=None)
    wall = make_wall(small)
    assert "intern-01" not in screen_text(small, wall)


def test_typing_edits_the_prompt_buffer(console: Console) -> None:
    wall = make_wall(console)
    for key in "shipx":
        assert wall.handle_key(key) is None
    wall.handle_key("backspace")
    assert wall.buffer == "ship"
    assert wall.sim.energy > 0
    assert wall.handle_key("esc") is None
    assert wall.buffer == ""
    wall.handle_key("left")
    assert wall.buffer == ""


def test_enter_submits_the_stripped_prompt(console: Console) -> None:
    wall = make_wall(console)
    for key in "  hi  ":
        wall.handle_key(key)
    assert wall.handle_key("enter") == "hi"
    assert wall.buffer == ""
    assert wall.handle_key("enter") == ""


def test_escape_on_an_empty_prompt_submits_quit(console: Console) -> None:
    assert make_wall(console).handle_key("esc") == "quit"


def test_ship_it_twice_wraps_up_then_launches(console: Console) -> None:
    session, sim = make_session(console, app="deploy")
    work = start(WorkStage(), session)
    type_line(work, "ship it")
    assert work.is_done
    assert work.next_stage is None
    wrap = start(WrapStage(), session)
    assert "wrapping up" in screen_text(console, wrap)
    assert not wrap.is_done
    advance(wrap, 20)
    assert wrap.is_done
    assert wrap.next_stage is None
    assert sim.is_all_done
    ready = start(ReadyStage(), session)
    text = screen_text(console, ready)
    assert "all 6 agents done" in text
    assert "ship it?" in text
    type_line(ready, "SHIP IT!!")
    assert ready.is_done
    assert ready.next_stage is None
    ship = start(ShipStage(), session)
    advance(ship, 1)
    assert "git push origin main --force" in screen_text(console, ship)
    assert not ship.is_done
    advance(ship, 3)
    assert ship.is_done
    assert "launching deploy…" in screen_text(console, ship)


def test_the_launch_line_names_the_then_command(console: Console) -> None:
    session, _ = make_session(console)
    session.then = "cmatrix -b"
    ship = start(ShipStage(), session)
    advance(ship, 4)
    assert "launching cmatrix…" in screen_text(console, ship)


def test_the_prompt_survives_a_stage_change(console: Console) -> None:
    session, _ = make_session(console)
    work = start(WorkStage(), session)
    type_line(work, "ship it")
    for key in "draft":
        work.on_key(key)
    wrap = start(WrapStage(), session)
    assert wrap.wall is work.wall
    assert wrap.wall.buffer == "draft"


def test_enter_on_an_empty_prompt_launches_once_ready(console: Console) -> None:
    session, _ = make_session(console)
    work = start(WorkStage(), session)
    work.on_key("enter")
    assert not work.is_done
    type_line(work, "lgtm")
    assert work.is_done
    wrap = start(WrapStage(), session)
    advance(wrap, 20)
    ready = start(ReadyStage(), session)
    ready.on_key("enter")
    assert ready.is_done


def test_other_text_is_broadcast_and_spawn_adds_an_agent(console: Console) -> None:
    session, sim = make_session(console)
    work = start(WorkStage(), session)
    type_line(work, "make it pop")
    assert ("you", "make it pop") in sim.reports
    type_line(work, "spawn")
    assert len(sim.agents) == 7
    assert not work.is_done


@pytest.mark.parametrize("line", ["q", "quit", ":q"])
def test_quit_words_abandon_the_run(console: Console, line: str) -> None:
    session, _ = make_session(console)
    work = start(WorkStage(), session)
    type_line(work, line)
    assert work.is_done
    assert work.next_stage == "abandon"


def test_escape_abandons_from_every_wall_stage(console: Console) -> None:
    session, _ = make_session(console)
    work = start(WorkStage(), session)
    type_line(work, "ship it")
    wrap = start(WrapStage(), session)
    wrap.on_key("esc")
    assert wrap.next_stage == "abandon"
    advance(wrap, 20)
    ready = start(ReadyStage(), session)
    ready.on_key("esc")
    assert ready.is_done
    assert ready.next_stage == "abandon"


def test_auto_ships_and_launches_by_itself(console: Console) -> None:
    session, _ = make_session(console)
    session.auto = 1.0
    work = start(WorkStage(), session)
    advance(work, 0.5)
    assert not work.is_done
    advance(work, 1)
    assert work.is_done
    wrap = start(WrapStage(), session)
    advance(wrap, 20)
    ready = start(ReadyStage(), session)
    advance(ready, 2)
    assert not ready.is_done
    advance(ready, 1)
    assert ready.is_done


def footer_text(console: Console, screen: Wall | ScreenStage) -> str:
    return screen_text(console, screen).splitlines()[-1]


def test_empty_prompt_says_who_you_are_talking_to(console: Console) -> None:
    wall = make_wall(console)
    footer = footer_text(console, wall)
    assert f"Message {wall.sim.orchestrator}" in footer
    assert "'ship it' to ship" in footer
    assert "mash" not in screen_text(console, wall)
    for key in "hi":
        wall.handle_key(key)
    assert f"Message {wall.sim.orchestrator}" not in footer_text(console, wall)


def test_header_stops_counting_once_everyone_is_done(console: Console) -> None:
    session, _ = make_session(console)
    type_line(start(WorkStage(), session), "ship it")
    advance(start(WrapStage(), session), 20)
    ready = start(ReadyStage(), session)
    header = screen_text(console, ready).splitlines()[0]
    advance(ready, 10)
    assert screen_text(console, ready).splitlines()[0] == header


def test_spawning_after_ship_it_is_ignored_and_totals_stay_frozen(
    console: Console,
) -> None:
    session, sim = make_session(console)
    type_line(start(WorkStage(), session), "ship it")
    wrap = start(WrapStage(), session)
    type_line(wrap, "spawn")  # while wrapping up
    assert len(sim.agents) == 6
    advance(wrap, 20)
    assert wrap.is_done
    snapshot = (sim.run_time, sim.total_calls, sim.total_tokens, sim.cost)
    ready = start(ReadyStage(), session)
    type_line(ready, "spawn")  # after everyone is done
    advance(ready, 1)
    assert len(sim.agents) == 6
    assert sim.is_all_done
    assert (sim.run_time, sim.total_calls, sim.total_tokens, sim.cost) == snapshot


def test_placeholder_only_shows_while_agents_are_running(console: Console) -> None:
    session, _ = make_session(console)
    type_line(start(WorkStage(), session), "ship it")
    wrap = start(WrapStage(), session)
    assert "Message" not in footer_text(console, wrap)


def test_escape_during_the_launch_abandons_like_before(console: Console) -> None:
    session, _ = make_session(console)
    type_line(start(WorkStage(), session), "ship it")
    advance(start(WrapStage(), session), 20)
    type_line(start(ReadyStage(), session), "ship it")
    ship = start(ShipStage(), session)
    ship.on_key("esc")
    assert ship.is_done
    assert ship.next_stage == "abandon"


def test_quit_during_the_launch_abandons(console: Console) -> None:
    session, _ = make_session(console)
    type_line(start(WorkStage(), session), "ship it")
    advance(start(WrapStage(), session), 20)
    type_line(start(ReadyStage(), session), "ship it")
    ship = start(ShipStage(), session)
    type_line(ship, "q")
    assert ship.next_stage == "abandon"
