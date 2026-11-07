"""The built-in stages: work, wrap up, get ready, ship, launch, receipt."""

import subprocess
import sys
from collections.abc import Iterable

from rich.markup import escape

from agentic_larp._flow import END, ScreenStage, Session
from agentic_larp._wall import ACCENT
from agentic_larp.apps._base import app_registry

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override

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


class WorkStage(ScreenStage):
    """The agents work until you type "ship it" (or demo mode does)."""

    mode = "running"

    @override
    def update(self) -> None:
        """Ship by itself once demo mode's time is up."""
        auto = self.session.auto
        if auto is not None and self.wall.sim.now >= auto:
            self.submit("ship it")

    @override
    def on_ship(self, text: str) -> None:
        """Tell the agents to wrap up.

        Args:
            text: The line.
        """
        sim = self.wall.sim
        sim.reports.append(("you", text))
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
            sim.reports.append((sim.orchestrator, done))
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
        self.finish()

    @override
    def on_ship(self, text: str) -> None:
        """Ship.

        Args:
            text: The line.
        """
        self.wall.sim.reports.append(("you", text))
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
            apps = app_registry()
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
            :data:`~agentic_larp.END`.
        """
        session.release_screen()
        if session.sim is not None:
            session.console.print(
                f"[dim]{len(session.sim.agents)} agents dismissed. nothing was built. as always.[/]"
            )
        return END
