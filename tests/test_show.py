import random
from collections.abc import Callable

import pytest
from rich.console import Console

from agentic_larp import (
    LogLine,
    ShowSettings,
    Sim,
    SwarmSettings,
    Theater,
    pick_scenario,
    render_entry,
)
from support import FakeClock, ScriptedKeys


def make_theater(console: Console, settings: ShowSettings | None = None) -> Theater:
    sim = Sim(pick_scenario(None, "prod"), SwarmSettings(agents=6), random.Random(4))
    return Theater(sim, console, settings)


def screen_text(console: Console, theater: Theater) -> str:
    with console.capture() as capture:
        console.print(theater.render(), height=console.height)
    return capture.get()


def type_line(theater: Theater, text: str) -> None:
    for key in text:
        theater.handle_key(key)
    theater.handle_key("enter")


def advance(theater: Theater, seconds: float, dt: float = 0.05) -> None:
    for _ in range(int(seconds / dt)):
        theater.step(dt)


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
    theater = make_theater(console)
    advance(theater, 2)
    text = screen_text(console, theater)
    for agent in theater.sim.agents:
        assert agent.name in text
    assert "intern-01" in text
    assert "orchestrating 6" in text
    assert "type 'ship it'" in text


def test_tiny_terminal_hides_the_swarm() -> None:
    small = Console(width=80, height=20, force_terminal=True, color_system=None)
    theater = make_theater(small)
    assert "intern-01" not in screen_text(small, theater)


def test_typing_edits_the_prompt_buffer(console: Console) -> None:
    theater = make_theater(console)
    for key in "shipx":
        theater.handle_key(key)
    theater.handle_key("backspace")
    assert theater.buffer == "ship"
    assert theater.sim.energy > 0
    theater.handle_key("esc")
    assert theater.buffer == ""
    assert theater.stage == "running"
    theater.handle_key("left")
    assert theater.buffer == ""


def test_ship_it_twice_wraps_up_then_launches(console: Console) -> None:
    theater = make_theater(console, ShowSettings(launch_label="deploy"))
    type_line(theater, "ship it")
    assert theater.stage == "wrapping"
    assert "wrapping up" in screen_text(console, theater)
    advance(theater, 20)
    assert theater.stage == "ready"
    assert theater.sim.is_all_done
    text = screen_text(console, theater)
    assert "all 6 agents done" in text
    assert "ship it?" in text
    type_line(theater, "SHIP IT!!")
    assert theater.stage == "launching"
    advance(theater, 1)
    assert "git push origin main --force" in screen_text(console, theater)
    assert not theater.is_launched
    advance(theater, 3)
    assert theater.is_launched
    assert theater.launch_lines[-1][0] == "  ⎿  launching deploy…"


def test_enter_on_an_empty_prompt_launches_once_ready(console: Console) -> None:
    theater = make_theater(console)
    theater.handle_key("enter")
    assert theater.stage == "running"
    type_line(theater, "lgtm")
    advance(theater, 20)
    theater.handle_key("enter")
    assert theater.stage == "launching"


def test_other_text_is_broadcast_and_spawn_adds_an_agent(console: Console) -> None:
    theater = make_theater(console)
    type_line(theater, "make it pop")
    assert ("you", "make it pop") in theater.sim.reports
    type_line(theater, "spawn")
    assert len(theater.sim.agents) == 7


@pytest.mark.parametrize("line", ["q", "quit", ":q"])
def test_quit_words_exit(console: Console, line: str) -> None:
    theater = make_theater(console)
    type_line(theater, line)
    assert theater.stage == "exit"


def test_run_returns_true_once_auto_ships(console: Console, clock: FakeClock) -> None:
    theater = make_theater(console, ShowSettings(auto=1.0))
    assert theater.run()
    assert theater.is_launched
    assert clock.now > 1.0


def test_run_returns_false_on_escape(
    console: Console,
    clock: FakeClock,
    make_keys: Callable[..., ScriptedKeys],
) -> None:
    theater = make_theater(
        console, ShowSettings(keys=make_keys((0.5, "a"), (1.0, "esc"), (1.0, "esc")))
    )
    assert not theater.run()
    assert 1.0 <= clock.now < 2.0


def test_pace_speeds_up_the_whole_show(console: Console, clock: FakeClock) -> None:
    theater = make_theater(console, ShowSettings(auto=5.0, pace=10.0))
    assert theater.run()
    assert clock.now < 3.0
