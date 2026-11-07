"""The built-in stages: plan, work, wrap up, get ready, ship, launch, receipt."""

import math
import subprocess
import sys
from collections.abc import Iterable

from rich.console import Group, RenderableType
from rich.layout import Layout
from rich.markup import escape
from rich.table import Table
from rich.text import Text

from agentic_larp._draw import ACCENT
from agentic_larp._flow import END, ScreenStage, Session
from agentic_larp.apps._base import app_registry

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override

PLAN_SECONDS = 2.0
_PLAN_COLUMN_WIDTH = 30
_AUTO_SHIP_DELAY = 2.5
_LAUNCH_SECONDS = 3.2
_UNKNOWN_APP = 2


def describe_unknown_app(name: str, apps: Iterable[str]) -> str:
    """Build the message for an app name nobody registered.

    Args:
        name: The name that was asked for.
        apps: The names that exist.

    Returns:
        Console markup.
    """
    return f"[red]no app called {escape(repr(name))}.[/] try: {', '.join(apps)}"


class PlanStage(ScreenStage):
    """Show every agent's todo list before any work starts."""

    mode = "running"

    @override
    def start(self) -> None:
        """Start the plan's own clock."""
        self._elapsed = 0.0

    @override
    def on_key(self, key: str) -> bool:
        """Skip the plan on any key, and pass the key on to the prompt.

        Args:
            key: A key name.

        Returns:
            ``False``, since the plan is over.
        """
        self.finish()
        self.wall.handle_key(key)
        return False

    @override
    def tick(self, dt: float) -> bool:
        """Count down the plan without advancing the swarm.

        Args:
            dt: Real seconds since the previous frame.

        Returns:
            ``False`` once the plan is over.
        """
        self._elapsed += dt * self.session.pace
        if self._elapsed >= PLAN_SECONDS:
            self.finish()
        return not self.is_done

    @override
    def render(self) -> RenderableType:
        """Build the todo lists.

        Returns:
            The wall's header and prompt around every agent's todos.
        """
        sim = self.wall.sim
        width, height = self.wall.console.size
        header, header_rows = self.wall.draw_header()
        footer, footer_rows = self.wall.draw_footer(header_rows)
        body = max(1, height - header_rows - footer_rows - 1)
        count = len(sim.agents)
        most = max(len(agent.todos) for agent in sim.agents)
        columns = 1
        for candidate in range(1, max(1, width // _PLAN_COLUMN_WIDTH) + 1):
            columns = candidate
            if body // math.ceil(count / candidate) >= most + 2:
                break
        shown = max(1, body // math.ceil(count / columns) - 2)
        grid = Table.grid(padding=(0, 2), expand=True)
        for _ in range(columns):
            grid.add_column(ratio=1, no_wrap=True, overflow="ellipsis")
        blocks = []
        for agent in sim.agents:
            todos = [todo.text for todo in agent.todos]
            if len(todos) > shown:
                hidden = len(todos) - shown + 1
                todos = [*todos[: shown - 1], f"+{hidden} more"]
            lines = [Text(agent.name, style="bold", no_wrap=True, overflow="ellipsis")]
            lines += [
                Text(f"  ☐ {text}", no_wrap=True, overflow="ellipsis") for text in todos
            ]
            blocks.append(Group(*lines, Text("")))
        for start in range(0, len(blocks), columns):
            row: list[RenderableType] = list(blocks[start : start + columns])
            row += [Text("")] * (columns - len(row))
            grid.add_row(*row)
        heading = Text.assemble(
            ("● ", "green"),
            ("TodoWrite", "bold"),
            (f"({sim.orchestrator}: {count} agents)", "dim"),
        )
        parts = [Layout(Group(heading, grid))]
        if header_rows:
            parts.insert(0, Layout(header, size=header_rows))
        if footer_rows:
            parts.append(Layout(footer, size=footer_rows))
        layout = Layout()
        layout.split_column(*parts)
        return layout


class WorkStage(ScreenStage):
    """The agents work until they converge or you type "ship it"."""

    mode = "running"

    @override
    def update(self) -> None:
        """Move on once the swarm converges; ship once demo mode's time is up."""
        sim = self.wall.sim
        if sim.is_converged:
            done = f"all {len(sim.agents)} agents done. ready to ship."
            sim.report(sim.orchestrator, done)
            self.finish("ready")
            return
        auto = self.session.auto
        if auto is not None and sim.now >= auto:
            self.submit("ship it")

    @override
    def on_ship(self, text: str) -> None:
        """Tell the agents to wrap up.

        Args:
            text: The line.
        """
        sim = self.wall.sim
        sim.report("you", text)
        sim.ship()
        self.finish()

    @override
    def on_spawn(self) -> None:
        """Add an agent."""
        self.wall.sim.spawn_agent()


class WrapStage(ScreenStage):
    """The agents finish what they were doing."""

    mode = "wrapping"

    @override
    def update(self) -> None:
        """Finish once every agent is done."""
        sim = self.wall.sim
        if sim.is_all_done:
            done = f"all {len(sim.agents)} agents done. ready to ship."
            sim.report(sim.orchestrator, done)
            self.finish()


class ReadyStage(ScreenStage):
    """Everyone is done; one more "ship it" (or a bare enter) ships."""

    mode = "ready"

    @override
    def update(self) -> None:
        """Ship by itself shortly after getting here, in demo mode."""
        if (
            self.session.auto is not None
            and self.wall.sim.now - self.wall.mode_since > _AUTO_SHIP_DELAY
        ):
            self.submit("ship it")

    @override
    def on_empty(self) -> None:
        """Ship."""
        self.wall.sim.start_ship()
        self.finish()

    @override
    def on_ship(self, text: str) -> None:
        """Ship.

        Args:
            text: The line.
        """
        self.wall.sim.report("you", text)
        self.wall.sim.start_ship()
        self.finish()


class ShipStage(ScreenStage):
    """Push to main and announce the payoff."""

    mode = "launching"

    @override
    def start(self) -> None:
        """Write the launch sequence."""
        session = self.session
        if bool(session.then):
            label = (session.then or "").split()[0]
        elif session.app != "none":
            label = session.app
        else:
            label = "it"
        self.wall.launch_lines = [
            ("● Bash(git add -A && git commit -m 'ship it')", "bold"),
            (
                f"  ⎿  [main 4a20d69] ship it · {self.wall.sim.total_calls:,} calls",
                "dim",
            ),
            ("● Bash(git push origin main --force)", "bold"),
            ("  ⎿  ✓ pushed (no one reviewed this)", "green"),
            (f"● Bash(./{label})", "bold"),
            (f"  ⎿  launching {label}…", ACCENT),
        ]

    @override
    def update(self) -> None:
        """Finish once the launch sequence has played."""
        if self.wall.sim.now - self.wall.mode_since > _LAUNCH_SECONDS:
            self.finish()


class LaunchStage:
    """Run the shell command or the payoff app."""

    def run(self, session: Session) -> str | None:
        """Hand the terminal over.

        Args:
            session: The session to run in.

        Returns:
            Always ``None``.
        """
        session.release_screen()
        if bool(session.then):
            session.exit_code = subprocess.call(session.then, shell=True)  # noqa: S602 - the user's own command; running it is the feature
        elif session.app != "none":
            apps = (
                app_registry(session.on_error) if session.apps is None else session.apps
            )
            if session.app not in apps:
                session.console.print(describe_unknown_app(session.app, apps))
                session.exit_code = _UNKNOWN_APP
            else:
                apps[session.app](session.app_context())
        return None


class ReceiptStage:
    """Print what was shipped."""

    def run(self, session: Session) -> str | None:
        """Print the receipt, if there was a swarm.

        Args:
            session: The session to run in.

        Returns:
            Always ``None``.
        """
        session.release_screen()
        sim = session.sim
        if sim is not None:
            session.console.print(
                f"[bold green]✓ shipped[/] [bold]{escape(sim.task)}[/] [dim]· {len(sim.agents)} agents · "
                f"{sim.total_calls:,} tool calls · ${sim.cost:,.2f} of imaginary compute[/]",
            )
        return None


class AbandonStage:
    """Print the dismissal and end the session."""

    def run(self, session: Session) -> str | None:
        """Dismiss the agents.

        Args:
            session: The session to run in.

        Returns:
            :data:`~agentic_larp.stages.END`.
        """
        session.release_screen()
        if session.sim is not None:
            session.console.print(
                f"[dim]{len(session.sim.agents)} agents dismissed. nothing was built. as always.[/]"
            )
        return END
