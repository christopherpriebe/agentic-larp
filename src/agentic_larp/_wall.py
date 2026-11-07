"""The agent wall: a screen of fake agents furiously doing nothing."""

import math
from collections.abc import Iterator
from typing import Literal, TypeAlias

from rich import box
from rich.console import Console, ConsoleOptions, Group
from rich.layout import Layout
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from agentic_larp._grid import Grid
from agentic_larp._log import LogLine
from agentic_larp._sim import Agent, Sim, format_duration, format_tokens

SPINNER = "·✢✳✶✻✽✻✶✳✢"
ACCENT = "#e8875b"
BORDER = "#3a4a5a"
_DIFF_STYLES = {"-": "white on #7a1f1f", "+": "white on #1f6b2c"}
PANEL_MIN_WIDTH = 38
PANEL_MIN_HEIGHT = 7
_HEADER_HEIGHT = 4
_TILE_WIDTH = 15
_TALL_TERMINAL = 34
_BUFFER_LIMIT = 60
_LAUNCH_LINE_SECONDS = 0.45
SPOTLIGHT_HOLD = 2.0


def spinner(now: float, offset: float = 0.0) -> str:
    """Return the spinner frame for a moment in time.

    Args:
        now: Seconds since start.
        offset: Phase shift, so neighbouring spinners don't move in lockstep.

    Returns:
        One character.
    """
    return SPINNER[int((now + offset) * 10) % len(SPINNER)]


def render_entry(entry: LogLine, width: int) -> Text:
    """Render one log line at exactly the given width.

    Args:
        entry: A line from an agent's log.
        width: Cells available.

    Returns:
        A single, padded line.
    """
    if entry.kind == "tool":
        line = Text.assemble(
            ("● ", "green"),
            (entry.label, "bold"),
            ("(", "dim"),
            entry.text,
            (")", "dim"),
        )
    elif entry.kind == "diff":
        line = Text(
            f"{entry.number:>3} {entry.label} {entry.text}",
            style=_DIFF_STYLES[entry.label],
        )
    elif entry.kind == "result":
        line = Text.assemble(("  ⎿  ", "dim"), (entry.text, entry.label))
    elif entry.kind == "done":
        line = Text(entry.text, style="bold green")
    else:
        line = Text(entry.text, style="bold white")
    line.no_wrap = True
    line.truncate(width, overflow="ellipsis", pad=True)
    return line


class AgentBody:
    """The tail of an agent's log, one line per entry, fitted to its panel."""

    def __init__(self, agent: Agent) -> None:
        self.agent = agent

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> Iterator[Text]:
        height = options.height or PANEL_MIN_HEIGHT
        entries = list(self.agent.log)[-height:]
        lines = [Text("")] * (height - len(entries))
        lines += [render_entry(entry, options.max_width) for entry in entries]
        yield Text("\n", no_wrap=True).join(lines)


Mode: TypeAlias = Literal["running", "wrapping", "ready", "launching"]


class Wall:
    """The agent wall: panels, the swarm strip, the header and the prompt.

    The wall only draws and edits the prompt; the stages decide what a
    submitted line means. Its :attr:`mode` picks the header and footer text.

    Attributes:
        sim: The swarm on show.
        console: Where the wall is sized against.
        grid: Fixed feed grid with spotlight rotation, or ``None`` to fit the
            terminal.
        buffer: The prompt line being typed.
        mode: Which stage the wall is dressed for.
        mode_since: Simulation time the mode last changed.
        launch_lines: The launch sequence shown while launching.
    """

    def __init__(
        self,
        sim: Sim,
        console: Console,
        *,
        grid: Grid | None = None,
        pace: float = 1.0,
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
            key: A key name from :func:`agentic_larp.parse_keys`.

        Returns:
            The submitted line (stripped, possibly empty) on enter, ``"quit"``
            on escape with an empty prompt, otherwise ``None``.
        """
        if key == "esc" and not self.buffer:
            return "quit"
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
    def render(self) -> Layout:
        """Build the whole screen for the current frame.

        Returns:
            A layout sized to the console.
        """
        width, height = self.console.size
        sim = self.sim
        agents = self.visible_agents()
        if self.grid is None:
            columns = max(1, min(len(agents), width // PANEL_MIN_WIDTH))
            rows = math.ceil(len(agents) / columns)
        else:
            columns, rows = self.grid.columns, self.grid.rows
        swarm_rows = 0
        if sim.interns:
            per_row = max(1, width // _TILE_WIDTH)
            swarm_rows = min(
                2 if height >= _TALL_TERMINAL else 1,
                math.ceil(len(sim.interns) / per_row),
            )
            body_height = height - _HEADER_HEIGHT - 1 - (swarm_rows * 2 + 1)
            if body_height < rows * PANEL_MIN_HEIGHT:
                swarm_rows = 0

        layout = Layout()
        parts = [
            Layout(self.render_header(), name="header", size=_HEADER_HEIGHT),
            Layout(name="body"),
        ]
        if swarm_rows:
            parts.append(
                Layout(self.render_swarm(width, swarm_rows), size=swarm_rows * 2 + 1)
            )
        parts.append(Layout(self.render_footer(), size=1))
        layout.split_column(*parts)

        row_layouts = []
        for row in range(rows):
            cells = [
                Layout(self.render_agent(agent))
                for agent in agents[row * columns : (row + 1) * columns]
            ]
            cells += [Layout(Text(" ")) for _ in range(columns - len(cells))]
            row_layout = Layout()
            row_layout.split_row(*cells)
            row_layouts.append(row_layout)
        layout["body"].split_column(*row_layouts)
        return layout

    def render_header(self) -> Group:
        """Build the orchestrator line and its latest reports.

        Returns:
            Four lines.
        """
        sim = self.sim
        if self.mode in {"ready", "launching"}:
            status = Text.assemble(
                ("✓ ", "bold green"),
                (f"all {len(sim.agents)} agents done", "green"),
            )
        else:
            word = "wrapping up" if self.mode == "wrapping" else "orchestrating"
            status = Text.assemble(
                (spinner(sim.now) + " ", ACCENT), f"{word} {sim.running}"
            )
        status.append(
            f" · {format_duration(sim.run_time)} · ↓ {format_tokens(sim.total_tokens)} · "
        )
        status.append(f"${sim.cost:,.2f}", style="bold yellow")
        top = Table.grid(expand=True)
        top.add_column(no_wrap=True)
        top.add_column(ratio=1)
        top.add_column(no_wrap=True, justify="right")
        title = Text.assemble(
            ("❯ ", "bold cyan"),
            (sim.orchestrator, "bold"),
            (f"  {sim.task} ", "dim italic"),
        )
        top.add_row(title, Rule(style=BORDER), Text(" ") + status)

        lines: list[Table | Text] = [top]
        if self.mode == "launching":
            shown = int((sim.now - self.mode_since) / _LAUNCH_LINE_SECONDS) + 1
            lines += [
                Text(line, style=style, no_wrap=True, overflow="ellipsis")
                for line, style in self.launch_lines[:shown][-3:]
            ]
        else:
            for who, message in list(sim.reports)[-3:]:
                if who == "you":
                    style = "bold cyan"
                elif who == sim.orchestrator:
                    style = f"bold {ACCENT}"
                else:
                    style = "bold"
                line = Text.assemble((f"{who:<11}", style), (message, "#c9d1d9"))
                line.no_wrap, line.overflow = True, "ellipsis"
                lines.append(line)
        lines += [Text("")] * (_HEADER_HEIGHT - len(lines))
        return Group(*lines)

    def render_agent(self, agent: Agent) -> Panel:
        """Build one agent's panel.

        Args:
            agent: The agent to draw.

        Returns:
            A bordered panel with a live title and footer.
        """
        sim = self.sim
        if agent.is_done:
            icon, color, verb = "✓", "green", "Done"
        else:
            icon = spinner(sim.now, hash(agent.name) % 7 / 10)
            color = ACCENT
            verb = "Committing…" if agent.finish_at is not None else f"{agent.verb}…"
        title = Text.assemble(
            (f" {icon} ", f"bold {color}"),
            (agent.name, "bold"),
            (f" · {agent.area} ", "dim"),
        )
        stats = f" {format_duration(sim.elapsed(agent))} · ↓ {format_tokens(agent.tokens)} · "
        subtitle = Text.assemble((stats, "dim"), (verb, f"italic {color}"), " ")
        return Panel(
            AgentBody(agent),
            title=title,
            title_align="left",
            subtitle=subtitle,
            subtitle_align="left",
            box=box.ROUNDED,
            border_style="green" if agent.is_done else BORDER,
            padding=(0, 1),
        )

    def render_swarm(self, width: int, rows: int) -> Group:
        """Build the strip of intern tiles.

        Args:
            width: Console width.
            rows: How many rows of tiles fit.

        Returns:
            A labelled rule over a grid of tiles.
        """
        sim = self.sim
        per_row = max(1, width // _TILE_WIDTH)
        visible = sim.interns[: per_row * rows]
        grid = Table.grid(padding=(0, 1), expand=True)
        for _ in range(min(per_row, len(visible))):
            grid.add_column(ratio=1, no_wrap=True)
        for row in range(rows):
            cells: list[Group | Text] = []
            for index, intern in enumerate(
                visible[row * per_row : (row + 1) * per_row]
            ):
                if intern.is_done:
                    head = Text.assemble((intern.name, "bold"), (" ✓", "green"))
                    body = Text(
                        f"✓ {format_duration(intern.frozen_elapsed)}", style="green"
                    )
                else:
                    mark = " " + spinner(sim.now, index / 10)
                    head = Text.assemble((intern.name, "bold"), (mark, ACCENT))
                    added = intern.task.startswith("+")
                    body = Text(intern.task, style="#e5c07b" if added else "#c9d1d9")
                for line in (head, body):
                    line.no_wrap, line.overflow = True, "ellipsis"
                cells.append(Group(head, body))
            cells += [Text("")] * (len(grid.columns) - len(cells))
            grid.add_row(*cells)
        label = Text(f" {sim.intern_model} ×{len(sim.interns)} ", style="dim")
        return Group(Rule(label, style=BORDER, align="left"), grid)

    def render_footer(self) -> Table:
        """Build the prompt line with the run's totals.

        Returns:
            One line.
        """
        sim = self.sim
        cursor = "█" if int(sim.now * 2) % 2 == 0 else " "
        if self.mode == "ready":
            prompt = Text.assemble(
                ("ship it? ❯ ", "bold green"),
                (self.buffer, "bold"),
                (cursor, "green"),
            )
            hint = "type 'ship it' (or just hit enter)"
        else:
            prompt = Text.assemble(
                ("❯ ", "bold cyan"), (self.buffer, "bold"), (cursor, "cyan")
            )
            if not self.buffer and self.mode == "running":
                prompt.append(f" Message {sim.orchestrator}…", style="dim")
            hint = "'ship it' to ship · esc to quit"
            if self.mode != "running":
                hint = ""
        totals = f"{sim.running}/{len(sim.agents)} running · {sim.total_calls:,} calls"
        right = Text.assemble(
            (totals, "dim"), (f"   {hint}" if hint else "", "dim italic")
        )
        grid = Table.grid(expand=True)
        grid.add_column(ratio=1, no_wrap=True)
        grid.add_column(no_wrap=True, justify="right")
        grid.add_row(prompt, right)
        return grid
