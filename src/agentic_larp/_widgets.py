"""Pluggable pieces of the wall: a widget per screen region."""

from __future__ import annotations

import math
import zlib
from typing import TYPE_CHECKING, Protocol, cast, runtime_checkable

from rich import box
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from agentic_larp._draw import ACCENT, BORDER, PANEL_MIN_HEIGHT, AgentBody, spinner
from agentic_larp._errors import LarpError
from agentic_larp._plugins import load_registry
from agentic_larp._sim import format_duration, format_tokens

if TYPE_CHECKING:
    from collections.abc import Callable

    from agentic_larp._sim import AgentView
    from agentic_larp._wall import Wall

REGIONS = ("header", "swarm", "question", "footer", "panel")
WIDGET_ENTRY_POINT_GROUP = "agentic_larp.widgets"
HEADER_HEIGHT = 4
FOOTER_HEIGHT = 1
TILE_WIDTH = 15
_TALL_TERMINAL = 34
_LAUNCH_LINE_SECONDS = 0.45


@runtime_checkable
class Widget(Protocol):
    """A full-width region of the wall: the header, the swarm strip or the footer."""

    def height(self, width: int, available: int) -> int:
        """Return the rows wanted; 0 hides the region.

        Args:
            width: Console width.
            available: Rows left for this region.
        """
        ...

    def render(self, width: int) -> RenderableType:
        """Draw the region.

        Args:
            width: Console width.
        """
        ...


@runtime_checkable
class PanelWidget(Protocol):
    """Draws one agent's panel in the body."""

    def render(self, agent: AgentView) -> RenderableType:
        """Draw the panel.

        Args:
            agent: The agent to draw.
        """
        ...


class HeaderWidget:
    """The orchestrator line and its latest reports."""

    def __init__(self, wall: Wall) -> None:
        self.wall = wall

    def height(self, width: int, available: int) -> int:  # noqa: ARG002 - fixed size
        """Return the rows wanted.

        Args:
            width: Console width.
            available: Rows left.

        Returns:
            Four.
        """
        return HEADER_HEIGHT

    def render(self, width: int) -> RenderableType:  # noqa: ARG002 - fits its cell
        """Build the orchestrator line and its latest reports.

        Args:
            width: Console width.

        Returns:
            Four lines.
        """
        sim = self.wall.sim
        if self.wall.mode in {"ready", "launching"}:
            status = Text.assemble(
                ("✓ ", "bold green"),
                (f"all {len(sim.agents)} agents done", "green"),
            )
        else:
            word = "wrapping up" if self.wall.mode == "wrapping" else "orchestrating"
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
        if self.wall.mode == "launching":
            shown = int((sim.now - self.wall.mode_since) / _LAUNCH_LINE_SECONDS) + 1
            lines += [
                Text(line, style=style, no_wrap=True, overflow="ellipsis")
                for line, style in self.wall.launch_lines[:shown][-3:]
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
        lines += [Text("")] * (HEADER_HEIGHT - len(lines))
        return Group(*lines)


class AgentPanel:
    """A bordered panel for one agent."""

    def __init__(self, wall: Wall) -> None:
        self.wall = wall

    def render(self, agent: AgentView) -> RenderableType:
        """Build one agent's panel.

        Args:
            agent: The agent to draw.

        Returns:
            A bordered panel with a live title and footer.
        """
        sim = self.wall.sim
        asked = sim.open_question
        if agent.is_done:
            icon, color, verb = "✓", "green", "Done"
        elif asked is not None and asked[0] is agent:
            icon, color, verb = "●", ACCENT, "Waiting for you"
        else:
            icon = spinner(sim.now, zlib.crc32(agent.name.encode()) % 7 / 10)
            color = ACCENT
            verb = "Committing…" if agent.finish_at is not None else f"{agent.verb}…"
        title = Text.assemble(
            (f" {icon} ", f"bold {color}"),
            (agent.name, "bold"),
            (f" · {agent.area} ", "dim"),
            (f"· {agent.todos_done}/{len(agent.todos)} ", "dim"),
        )
        if asked is not None and asked[0] is agent:
            title.append("· Waiting for you ", style=f"italic {ACCENT}")
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


class SwarmWidget:
    """The strip of intern tiles."""

    def __init__(self, wall: Wall) -> None:
        self.wall = wall

    def _wanted_rows(self, width: int) -> int:
        wall = self.wall
        interns = wall.sim.interns
        if not interns:
            return 0
        per_row = max(1, width // TILE_WIDTH)
        tall = wall.console.size.height >= _TALL_TERMINAL
        return min(2 if tall else 1, math.ceil(len(interns) / per_row))

    def height(self, width: int, available: int) -> int:
        """Return the rows wanted.

        Args:
            width: Console width.
            available: Rows left for the strip and the panels.

        Returns:
            Zero when there are no interns or the panels would get too small.
        """
        rows = self._wanted_rows(width)
        _, panel_rows = self.wall.grid_shape(width)
        if not rows or available - (rows * 2 + 1) < panel_rows * PANEL_MIN_HEIGHT:
            return 0
        return rows * 2 + 1

    def render(self, width: int) -> RenderableType:
        """Build the strip of intern tiles.

        Args:
            width: Console width.

        Returns:
            A labelled rule over a grid of tiles.
        """
        sim = self.wall.sim
        rows = self._wanted_rows(width)
        per_row = max(1, width // TILE_WIDTH)
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


class QuestionWidget:
    """The box an agent's question appears in; hidden when none is open."""

    def __init__(self, wall: Wall) -> None:
        self.wall = wall
        self._is_described = True
        self._has_hint = True

    def _box(self) -> RenderableType:
        asked = self.wall.sim.open_question
        if asked is None:
            return Text("")
        agent, question = asked
        cursor = self.wall.question_cursor
        lines: list[Text] = [Text(question.prompt, style="bold"), Text("")]
        for index, option in enumerate(question.options):
            chosen = index == cursor
            label = f"{index + 1}. {option.label}"
            if index == question.recommended:
                label += " (Recommended)"
            lines.append(
                Text.assemble(
                    ("❯ " if chosen else "  ", f"bold {ACCENT}"),
                    (label, f"bold {ACCENT}" if chosen else ""),
                )
            )
            if option.description and self._is_described:
                lines.append(Text(f"     {option.description}", style="dim"))
        if self._has_hint:
            lines += [
                Text(""),
                Text("↑/↓ · enter · esc picks the recommendation", style="dim italic"),
            ]
        title = Text.assemble((f" {agent.name} ", "bold"), ("asks ", "dim"))
        return Panel(
            Group(*lines),
            title=title,
            title_align="left",
            box=box.ROUNDED,
            border_style=ACCENT,
            padding=(0, 1),
        )

    def height(self, width: int, available: int) -> int:
        """Return the rows wanted.

        Args:
            width: Console width.
            available: Rows left.

        Returns:
            Zero when nothing is open, otherwise the rows the box fills;
            descriptions, then the hint, are dropped to fit ``available``.
        """
        if self.wall.sim.open_question is None:
            return 0
        console = self.wall.console
        options = console.options.update_width(width)
        rows = 0
        for self._is_described, self._has_hint in (
            (True, True),
            (False, True),
            (False, False),
        ):
            rows = len(console.render_lines(self._box(), options, pad=False))
            if rows <= available:
                break
        return rows

    def render(self, width: int) -> RenderableType:  # noqa: ARG002 - fits its cell
        """Build the question box.

        Args:
            width: Console width.

        Returns:
            A bordered box with the prompt and numbered options.
        """
        return self._box()


class FooterWidget:
    """The prompt line with the run's totals."""

    def __init__(self, wall: Wall) -> None:
        self.wall = wall

    def height(self, width: int, available: int) -> int:  # noqa: ARG002 - fixed size
        """Return the rows wanted.

        Args:
            width: Console width.
            available: Rows left.

        Returns:
            One.
        """
        return FOOTER_HEIGHT

    def render(self, width: int) -> RenderableType:  # noqa: ARG002 - fits its cell
        """Build the prompt line with the run's totals.

        Args:
            width: Console width.

        Returns:
            One line.
        """
        sim = self.wall.sim
        cursor = "█" if int(sim.now * 2) % 2 == 0 else " "
        if sim.open_question is not None:
            prompt = Text.assemble(
                ("❯ ", "bold cyan"), ("answer the question above", "dim")
            )
            hint = "1-4 · ↑/↓ · enter · esc"
        elif self.wall.mode == "ready":
            prompt = Text.assemble(
                ("ship it? ❯ ", "bold green"),
                (self.wall.buffer, "bold"),
                (cursor, "green"),
            )
            hint = "type 'ship it' (or just hit enter)"
        else:
            prompt = Text.assemble(
                ("❯ ", "bold cyan"), (self.wall.buffer, "bold"), (cursor, "cyan")
            )
            if not self.wall.buffer and self.wall.mode == "running":
                prompt.append(f" Message {sim.orchestrator}…", style="dim")
            hint = "'ship it' to ship · esc to quit"
            if self.wall.mode != "running":
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


def builtin_widgets() -> dict[str, Callable[[Wall], Widget | PanelWidget]]:
    """Return the built-in widget factory for each region.

    Returns:
        Region name mapped to a factory.
    """
    return {
        "header": HeaderWidget,
        "swarm": SwarmWidget,
        "question": QuestionWidget,
        "footer": FooterWidget,
        "panel": AgentPanel,
    }


def _check_widget(name: str, value: object) -> Callable[[Wall], Widget | PanelWidget]:
    if name not in REGIONS:
        message = f"not a region; use one of {', '.join(REGIONS)}"
        raise LarpError(message)
    if not callable(value):
        message = "not a widget factory"
        raise LarpError(message)
    return cast("Callable[[Wall], Widget | PanelWidget]", value)


def widget_registry(
    on_error: Callable[[str, Exception], None] | None = None,
) -> dict[str, Callable[[Wall], Widget | PanelWidget]]:
    """Return every widget factory by region: the built-ins, then plugins.

    Plugins register under the ``agentic_larp.widgets`` entry-point group,
    named after the region they replace; the loaded value is a class or
    function that takes the wall and returns a widget.

    Args:
        on_error: Called with the plugin name and the error for each plugin
            that fails to load or names an unknown region, which is then
            skipped. By default a failing plugin raises ``LarpError`` naming the group and plugin.

    Returns:
        Region name mapped to a factory.
    """
    return load_registry(
        WIDGET_ENTRY_POINT_GROUP,
        builtin_widgets(),
        check=_check_widget,
        on_error=on_error,
    )
