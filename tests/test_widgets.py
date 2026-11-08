import importlib.metadata
import random
from collections.abc import Callable
from dataclasses import dataclass

import pytest
from rich.console import Console, RenderableType
from rich.text import Text

from agentic_larp import LarpError
from agentic_larp.events import LineShown
from agentic_larp.packs import pick_scenario
from agentic_larp.sim import Agent, Sim, SwarmSettings
from agentic_larp.stages import PlanStage, Session, run_flow
from agentic_larp.widgets import (
    REGIONS,
    WIDGET_ENTRY_POINT_GROUP,
    AgentPanel,
    FooterWidget,
    HeaderWidget,
    SwarmWidget,
    Wall,
    widget_registry,
)
from support import FakeClock, ScriptedKeys, output

WIDTH, HEIGHT = 140, 44


def make_sim(*, interns: int = 8) -> Sim:
    settings = SwarmSettings(agents=4, interns=interns)
    return Sim([pick_scenario(None, "prod")], settings, random.Random(4))


def screen(wall: Wall) -> list[str]:
    console = wall.console
    with console.capture() as capture:
        console.print(wall.render(), height=console.height)
    return capture.get().splitlines()


def make_console() -> Console:
    return Console(width=WIDTH, height=HEIGHT, force_terminal=True, color_system=None)


class Banner:
    """A one-row widget that shows fixed text."""

    def __init__(self, text: str, rows: int = 1) -> None:
        self.text = text
        self.rows = rows

    def height(self, width: int, available: int) -> int:
        assert width > 0
        assert available > 0
        return self.rows

    def render(self, width: int) -> RenderableType:
        assert width > 0
        return Text("\n".join(f"{self.text} {row}" for row in range(self.rows)))


class Tag:
    """A panel widget that labels each agent."""

    def __init__(self, wall: Wall) -> None:
        self.wall = wall

    def render(self, agent: Agent) -> RenderableType:
        return Text(f"PANEL {agent.name}")


def test_regions_are_the_four_parts_of_the_wall() -> None:
    assert REGIONS == ("header", "swarm", "question", "footer", "panel")
    assert set(widget_registry()) >= set(REGIONS)


def test_the_default_widgets_render_the_same_wall() -> None:
    sim = make_sim()
    console = make_console()
    plain = Wall(sim, console)
    explicit = Wall(sim, console, widgets=widget_registry())
    assert screen(plain) == screen(explicit)
    text = "\n".join(screen(plain))
    assert "orchestrating 4" in text
    assert "intern-01" in text
    assert "Message" in text


def test_a_header_widget_replaces_only_the_header() -> None:
    sim = make_sim()
    widgets = {**widget_registry(), "header": lambda _wall: Banner("PLUGIN HEADER")}
    lines = screen(Wall(sim, make_console(), widgets=widgets))
    assert lines[0].startswith("PLUGIN HEADER")
    text = "\n".join(lines)
    assert sim.orchestrator not in lines[0]
    for agent in sim.agents:
        assert agent.name in text
    assert "Message" in lines[-1]


def test_a_panel_widget_draws_every_agent() -> None:
    sim = make_sim()
    widgets = {**widget_registry(), "panel": Tag}
    text = "\n".join(screen(Wall(sim, make_console(), widgets=widgets)))
    for agent in sim.agents:
        assert f"PANEL {agent.name}" in text


def test_a_zero_height_widget_is_hidden() -> None:
    sim = make_sim()
    widgets = {**widget_registry(), "swarm": lambda _wall: Banner("SWARM", rows=0)}
    text = "\n".join(screen(Wall(sim, make_console(), widgets=widgets)))
    assert "intern-01" not in text
    assert "SWARM" not in text


def test_a_widget_gets_the_rows_it_asks_for() -> None:
    sim = make_sim()
    widgets = {**widget_registry(), "footer": lambda _wall: Banner("FOOT", rows=2)}
    lines = screen(Wall(sim, make_console(), widgets=widgets))
    assert lines[-2].startswith("FOOT 0")
    assert lines[-1].startswith("FOOT 1")
    assert len(lines) == HEIGHT


class LineCounter:
    """A footer that counts lines through the event bus."""

    def __init__(self, wall: Wall) -> None:
        self.count = 0
        wall.sim.events.subscribe(LineShown, self.on_line)

    def on_line(self, _event: LineShown) -> None:
        self.count += 1

    def height(self, width: int, available: int) -> int:
        return 1 if width and available else 0

    def render(self, width: int) -> RenderableType:
        return Text(f"lines shown: {self.count}"[:width])


def test_a_widget_can_follow_the_sim_through_events() -> None:
    sim = make_sim()
    seen: list[LineShown] = []
    sim.events.subscribe(LineShown, seen.append)
    wall = Wall(
        sim, make_console(), widgets={**widget_registry(), "footer": LineCounter}
    )
    for _ in range(int(5 / 0.05)):
        wall.step(0.05)
    assert seen
    assert screen(wall)[-1].startswith(f"lines shown: {len(seen)}")


def test_an_oversized_widget_is_clamped_to_the_screen() -> None:
    sim = make_sim()
    widgets = {**widget_registry(), "header": lambda _wall: Banner("HUGE", rows=500)}
    lines = screen(Wall(sim, make_console(), widgets=widgets))
    assert len(lines) == HEIGHT
    assert lines[0].startswith("HUGE 0")


def test_the_built_in_widgets_are_public_and_wrappable() -> None:
    sim = make_sim()

    class LoudFooter:
        def __init__(self, wall: Wall) -> None:
            self.inner = FooterWidget(wall)

        def height(self, width: int, available: int) -> int:
            return self.inner.height(width, available)

        def render(self, width: int) -> RenderableType:
            return Text(f"LOUD {width}")

    wall = Wall(
        sim, make_console(), widgets={**widget_registry(), "footer": LoudFooter}
    )
    assert screen(wall)[-1].startswith("LOUD 140")
    defaults = widget_registry()
    assert defaults["header"] is HeaderWidget
    assert defaults["swarm"] is SwarmWidget
    assert defaults["footer"] is FooterWidget
    assert defaults["panel"] is AgentPanel


def test_the_swarm_renders_without_asking_its_height_first() -> None:
    sim = make_sim()
    swarm = SwarmWidget(Wall(sim, make_console()))
    console = make_console()
    with console.capture() as capture:
        console.print(swarm.render(WIDTH))
    assert "intern-01" in capture.get()


def test_the_plan_screen_respects_widget_heights(
    console: Console, clock: FakeClock
) -> None:
    sim = make_sim()
    session = Session(
        console=console,
        task=sim.task,
        sim=sim,
        rng=random.Random(1),
        keys=ScriptedKeys(clock),
    )
    widgets = {
        **widget_registry(),
        "header": lambda _wall: Banner("HIDDEN", rows=0),
        "footer": lambda _wall: Banner("FOOT", rows=2),
    }
    session.wall = Wall(sim, console, widgets=widgets)
    plan = PlanStage()
    plan.begin(session)
    with console.capture() as capture:
        console.print(plan.render(), height=console.height)
    lines = capture.get().splitlines()
    assert "HIDDEN" not in "\n".join(lines)
    assert lines[-2].startswith("FOOT 0")
    assert lines[-1].startswith("FOOT 1")


def test_an_unknown_region_is_an_error() -> None:
    with pytest.raises(LarpError, match="'sidebar'"):
        Wall(make_sim(), make_console(), widgets={"sidebar": lambda _wall: Banner("x")})


@dataclass
class FakeEntryPoint:
    name: str
    target: object

    def load(self) -> object:
        return self.target


def plugin_widgets(
    monkeypatch: pytest.MonkeyPatch, **widgets: Callable[[Wall], object]
) -> None:
    real = importlib.metadata.entry_points

    def fake_entry_points(*, group: str) -> object:
        if group == WIDGET_ENTRY_POINT_GROUP:
            return [FakeEntryPoint(name, target) for name, target in widgets.items()]
        return real(group=group)

    monkeypatch.setattr(importlib.metadata, "entry_points", fake_entry_points)


def header_plugin(_wall: Wall) -> Banner:
    return Banner("PLUGIN HEADER")


def test_a_plugin_named_after_a_region_replaces_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plugin_widgets(monkeypatch, header=header_plugin)
    assert widget_registry()["header"] is header_plugin


def test_the_show_uses_plugin_widgets(
    monkeypatch: pytest.MonkeyPatch, console: Console, clock: FakeClock
) -> None:
    plugin_widgets(monkeypatch, header=header_plugin)
    sim = make_sim()
    session = Session(
        console=console, task=sim.task, sim=sim, rng=random.Random(1), auto=1.0
    )
    assert run_flow(session) == 0
    assert "PLUGIN HEADER" in output(console)
    assert clock.now > 1.0
