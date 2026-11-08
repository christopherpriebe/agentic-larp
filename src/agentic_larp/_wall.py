"""The agent wall: a screen of fake agents furiously doing nothing."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from typing import Literal, TypeAlias

from rich.console import Console, RenderableType
from rich.layout import Layout
from rich.text import Text

from agentic_larp._errors import LarpError
from agentic_larp._grid import Grid
from agentic_larp._sim import Agent, Sim
from agentic_larp._widgets import (
    REGIONS,
    PanelWidget,
    Widget,
    builtin_widgets,
)

PANEL_MIN_WIDTH = 38
_BUFFER_LIMIT = 60
SPOTLIGHT_HOLD = 2.0


def _clamp(rows: int, available: int) -> int:
    return max(0, min(rows, available))


Mode: TypeAlias = Literal["running", "wrapping", "ready", "launching"]


class Wall:
    """The agent wall: panels, the swarm strip, the header and the prompt.

    The wall only draws and edits the prompt; the stages decide what a
    submitted line means. Its :attr:`mode` picks the header and footer text.
    Plugins should treat its attributes as read-only.

    Attributes:
        sim: The swarm on show.
        console: Where the wall is sized against.
        grid: Fixed feed grid with spotlight rotation, or ``None`` to fit the
            terminal.
        buffer: The prompt line being typed.
        mode: Which stage the wall is dressed for.
        mode_since: Simulation time the mode last changed.
        launch_lines: The launch sequence shown while launching.
        question_cursor: The highlighted option of the open question.
    """

    def __init__(
        self,
        sim: Sim,
        console: Console,
        *,
        grid: Grid | None = None,
        pace: float = 1.0,
        widgets: Mapping[str, Callable[[Wall], Widget | PanelWidget]] | None = None,
    ) -> None:
        self.sim = sim
        self.console = console
        self.grid = grid
        self.pace = pace
        self._spotlight: list[Agent] = []
        self._shown_since: list[float] = []
        self._last_shown: dict[str, float] = {}
        self._last_swap = 0.0
        self.buffer = ""
        self.mode: Mode = "running"
        self.mode_since = 0.0
        self.launch_lines: list[tuple[str, str]] = []
        self.question_cursor = 0
        factories = builtin_widgets()
        for region, factory in (widgets or {}).items():
            if region not in REGIONS:
                message = f"unknown widget region {region!r}; regions are {', '.join(REGIONS)}"
                raise LarpError(message)
            factories[region] = factory
        self._header = self._build_region(factories, "header")
        self._swarm = self._build_region(factories, "swarm")
        self._question = self._build_region(factories, "question")
        self._footer = self._build_region(factories, "footer")
        panel = factories["panel"](self)
        if not isinstance(panel, PanelWidget):
            message = "the 'panel' widget needs a render(agent) method"
            raise LarpError(message)
        self._panel = panel

    def _build_region(
        self,
        factories: Mapping[str, Callable[[Wall], Widget | PanelWidget]],
        region: str,
    ) -> Widget:
        built = factories[region](self)
        if not isinstance(built, Widget):
            message = f"the {region!r} widget needs height() and render() methods"
            raise LarpError(message)
        return built

    def set_mode(self, mode: Mode) -> None:
        """Dress the wall for a stage.

        Args:
            mode: The new mode.
        """
        self.mode = mode
        self.mode_since = self.sim.now

    def handle_key(self, key: str) -> str | None:
        """Apply one keypress to the prompt.

        Args:
            key: A key name from :func:`agentic_larp.keys.parse_keys`.

        Printable keys also poke the sim: the agents speed up as you type.

        Returns:
            The submitted line (stripped, possibly empty) on enter, otherwise
            ``None``.
        """
        if key == "enter":
            text = self.buffer.strip()
            self.buffer = ""
            return text
        if key == "backspace":
            self.buffer = self.buffer[:-1]
        elif key == "esc":
            self.buffer = ""
        elif len(key) == 1:
            self.buffer = (self.buffer + key)[-_BUFFER_LIMIT:]
            self.sim.poke(1.2)
        return None

    def step(self, dt: float) -> None:
        """Advance the simulation and the spotlight by one frame.

        Args:
            dt: Real seconds since the previous frame.
        """
        self.sim.tick(dt * self.pace)
        self._rotate_spotlight()

    def visible_agents(self) -> list[Agent]:
        """Return the agents that have a panel on screen right now.

        Returns:
            Every agent when there is no grid or it has room for all of them;
            otherwise exactly one agent per grid cell.
        """
        if not self._is_spotlight_active():
            return list(self.sim.agents)
        return list(self._spotlight)

    def _is_spotlight_active(self) -> bool:
        grid, agents = self.grid, self.sim.agents
        if grid is None or len(agents) <= grid.cells:
            self._spotlight = []
            return False
        if len(self._spotlight) != grid.cells:
            self._spotlight = agents[: grid.cells]
            self._shown_since = [self.sim.now] * grid.cells
        return True

    def _rotate_spotlight(self) -> None:
        if not self._is_spotlight_active():
            return
        now = self.sim.now
        for agent in self._spotlight:
            self._last_shown[agent.name] = now
        if now - self._last_swap < SPOTLIGHT_HOLD / len(self._spotlight):
            return
        ready = [
            cell
            for cell, since in enumerate(self._shown_since)
            if now - since >= SPOTLIGHT_HOLD
        ]
        shown = {agent.name for agent in self._spotlight}
        waiting = [agent for agent in self.sim.agents if agent.name not in shown]
        if not ready or not waiting:
            return
        cell = min(ready, key=lambda index: self._shown_since[index])
        incoming = min(
            waiting,
            key=lambda agent: (
                self._last_shown.get(agent.name, -math.inf),
                -agent.last_active,
            ),
        )
        self._spotlight[cell] = incoming
        self._shown_since[cell] = now
        self._last_swap = now

    # ---- rendering -------------------------------------------------------------
    def grid_shape(self, width: int) -> tuple[int, int]:
        """Return the panel grid for a console width.

        Args:
            width: Console width.

        Returns:
            Columns and rows.
        """
        if self.grid is not None:
            return self.grid.columns, self.grid.rows
        count = len(self.visible_agents())
        columns = max(1, min(count, width // PANEL_MIN_WIDTH))
        return columns, math.ceil(count / columns)

    def draw_header(self) -> tuple[RenderableType, int]:
        """Draw the header widget, for stages that lay out their own screen.

        Returns:
            The header and the rows it gets (0 hides it).
        """
        width, height = self.console.size
        rows = _clamp(self._header.height(width, height), height)
        return self._header.render(width), rows

    def draw_footer(self, header_rows: int) -> tuple[RenderableType, int]:
        """Draw the footer widget, for stages that lay out their own screen.

        Args:
            header_rows: Rows the header takes.

        Returns:
            The footer and the rows it gets (0 hides it).
        """
        width, height = self.console.size
        available = height - header_rows
        rows = _clamp(self._footer.height(width, available), available)
        return self._footer.render(width), rows

    def render(self) -> Layout:
        """Build the whole screen for the current frame.

        Returns:
            A layout sized to the console.
        """
        width, height = self.console.size
        agents = self.visible_agents()
        columns, rows = self.grid_shape(width)

        header, swarm, footer, panel = (
            self._header,
            self._swarm,
            self._footer,
            self._panel,
        )
        header_rows = _clamp(header.height(width, height), height)
        footer_rows = _clamp(
            footer.height(width, height - header_rows), height - header_rows
        )
        left = height - header_rows - footer_rows
        swarm_rows = _clamp(swarm.height(width, left), left)
        question_rows = _clamp(
            self._question.height(width, left - swarm_rows), left - swarm_rows
        )

        layout = Layout()
        parts = []
        if header_rows:
            parts.append(Layout(header.render(width), name="header", size=header_rows))
        parts.append(Layout(name="body"))
        if swarm_rows:
            parts.append(Layout(swarm.render(width), size=swarm_rows))
        if question_rows:
            parts.append(Layout(self._question.render(width), size=question_rows))
        if footer_rows:
            parts.append(Layout(footer.render(width), size=footer_rows))
        layout.split_column(*parts)

        row_layouts = []
        for row in range(rows):
            cells = [
                Layout(panel.render(agent))
                for agent in agents[row * columns : (row + 1) * columns]
            ]
            cells += [Layout(Text(" ")) for _ in range(columns - len(cells))]
            row_layout = Layout()
            row_layout.split_row(*cells)
            row_layouts.append(row_layout)
        layout["body"].split_column(*row_layouts)
        return layout
