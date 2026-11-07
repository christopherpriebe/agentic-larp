import random

import pytest
from rich.console import Console

from agentic_larp import (
    SPOTLIGHT_HOLD,
    Grid,
    LarpError,
    ShowSettings,
    Sim,
    SwarmSettings,
    Theater,
    pick_scenario,
)


def make_theater(
    agents: int, grid: Grid | None, width: int = 200, height: int = 50
) -> Theater:
    console = Console(
        width=width, height=height, force_terminal=True, color_system=None
    )
    sim = Sim(
        [pick_scenario(None, "prod")],
        SwarmSettings(agents=agents, interns=0),
        random.Random(8),
    )
    return Theater(sim, console, ShowSettings(grid=grid))


def panels_per_row(theater: Theater) -> list[int]:
    console = theater.console
    with console.capture() as capture:
        console.print(theater.render(), height=console.height)
    return [line.count("╭") for line in capture.get().splitlines() if "╭" in line]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("3x2", Grid(3, 2)),
        ("3X2", Grid(3, 2)),
        (" 4x1 ", Grid(4, 1)),
        ("10x10", Grid(10, 10)),
    ],
)
def test_grid_parse_reads_columns_by_rows(text: str, expected: Grid) -> None:
    assert Grid.parse(text) == expected


@pytest.mark.parametrize("text", ["3", "0x2", "2x0", "axb", "", "3x2x1", "-1x2"])
def test_grid_parse_rejects_bad_specs(text: str) -> None:
    with pytest.raises(LarpError, match="COLSxROWS"):
        Grid.parse(text)


def test_grid_cells() -> None:
    assert Grid(3, 2).cells == 6


def test_grid_draws_exactly_its_shape() -> None:
    assert panels_per_row(make_theater(6, Grid(3, 2))) == [3, 3]
    assert panels_per_row(make_theater(6, Grid(2, 3))) == [2, 2, 2]
    assert panels_per_row(make_theater(4, Grid(4, 1), width=80)) == [4]


def test_grid_with_fewer_agents_leaves_cells_blank() -> None:
    theater = make_theater(4, Grid(3, 2))
    assert panels_per_row(theater) == [3, 1]
    assert len(theater.visible_agents()) == 4


def test_without_a_grid_every_agent_is_visible() -> None:
    theater = make_theater(7, None)
    assert theater.visible_agents() == theater.sim.agents
    assert sum(panels_per_row(theater)) == 7


def test_spotlight_shows_one_agent_per_cell() -> None:
    theater = make_theater(20, Grid(3, 2))
    for _ in range(100):
        theater.step(0.05)
        visible = theater.visible_agents()
        assert len(visible) == 6
        assert len({agent.name for agent in visible}) == 6
    assert sum(panels_per_row(theater)) == 6


def test_spotlight_eventually_shows_every_agent() -> None:
    theater = make_theater(20, Grid(3, 2))
    seen: set[str] = set()
    for _ in range(int(120 / 0.05)):
        theater.step(0.05)
        seen |= {agent.name for agent in theater.visible_agents()}
    assert seen == {agent.name for agent in theater.sim.agents}


def test_spotlight_holds_each_cell_for_a_minimum_time() -> None:
    theater = make_theater(20, Grid(3, 2))
    occupant = [agent.name for agent in theater.visible_agents()]
    since = [0.0] * 6
    for _ in range(int(60 / 0.05)):
        theater.step(0.05)
        now = theater.sim.now
        for cell, agent in enumerate(theater.visible_agents()):
            if agent.name != occupant[cell]:
                assert now - since[cell] >= SPOTLIGHT_HOLD - 1e-9
                occupant[cell], since[cell] = agent.name, now


def test_header_counts_every_agent_not_just_visible_ones() -> None:
    theater = make_theater(20, Grid(3, 2))
    console = theater.console
    with console.capture() as capture:
        console.print(theater.render(), height=console.height)
    assert "orchestrating 20" in capture.get()


def test_spawning_past_the_grid_starts_the_spotlight() -> None:
    theater = make_theater(6, Grid(3, 2))
    assert theater.visible_agents() == theater.sim.agents
    for key in "spawn":
        theater.handle_key(key)
    theater.handle_key("enter")
    assert len(theater.sim.agents) == 7
    newcomer = theater.sim.agents[-1]
    shown: set[str] = set()
    for _ in range(int(30 / 0.05)):
        theater.step(0.05)
        visible = theater.visible_agents()
        assert len(visible) == 6
        assert len({agent.name for agent in visible}) == 6
        shown |= {agent.name for agent in visible}
    assert newcomer.name in shown


def test_spotlight_keeps_rotating_after_everyone_is_done() -> None:
    theater = make_theater(10, Grid(2, 2))
    theater.sim.ship()
    for _ in range(int(20 / 0.05)):
        theater.step(0.05)
    assert theater.sim.is_all_done
    seen: set[str] = set()
    for _ in range(int(40 / 0.05)):
        theater.step(0.05)
        seen |= {agent.name for agent in theater.visible_agents()}
    assert seen == {agent.name for agent in theater.sim.agents}
