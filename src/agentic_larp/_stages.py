"""The built-in stages: plan, work, wrap up, get ready, ship, launch, receipt, and abandon."""

import math
import subprocess
import sys
from collections.abc import Iterable

from rich.console import Group, RenderableType
from rich.layout import Layout
from rich.markup import escape
from rich.table import Table
from rich.text import Text

from agentic_larp._draw import ACCENT, spinner
from agentic_larp._events import QuestionAnswered
from agentic_larp._flow import END, ScreenStage, Session
from agentic_larp._questions import Question
from agentic_larp.apps._base import app_registry

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override

PLAN_SECONDS = 2.0
_PLAN_COLUMN_WIDTH = 30
_PLAN_DISPATCH_SHARE = 0.75
_AUTO_SHIP_DELAY = 2.5
_AUTO_ANSWER_DELAY = 2.5
_KEY_GRACE = 0.4
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
    names = ", ".join(escape(app) for app in apps)
    return f"[red]no app called {escape(repr(name))}.[/] try: {names}"


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
        step = dt * self.session.pace
        self._elapsed += step
        self.wall.sim.idle(step)
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
        ready = self._dispatched(count)
        for index, agent in enumerate(sim.agents):
            todos = [todo.text for todo in agent.todos]
            if len(todos) > shown:
                hidden = len(todos) - shown + 1
                todos = [*todos[: shown - 1], f"+{hidden} more"]
            if index < ready:
                mark = ("✓ ", "green")
            else:
                mark = (spinner(self._elapsed, offset=index * 0.3) + " ", ACCENT)
            name = Text.assemble(mark, (agent.name, "bold" if index < ready else "dim"))
            name.no_wrap, name.overflow = True, "ellipsis"
            lines = [name]
            lines += [
                Text(f"  ☐ {text}", no_wrap=True, overflow="ellipsis") for text in todos
            ]
            blocks.append(Group(*lines, Text("")))
        for start in range(0, len(blocks), columns):
            row: list[RenderableType] = list(blocks[start : start + columns])
            row += [Text("")] * (columns - len(row))
            grid.add_row(*row)
        if ready < count:
            bullet = (spinner(self._elapsed) + " ", ACCENT)
            note = f"({sim.orchestrator}: dispatching {ready}/{count} agents)"
        else:
            bullet, note = ("● ", "green"), f"({sim.orchestrator}: {count} agents)"
        heading = Text.assemble(bullet, ("TodoWrite", "bold"), (note, "dim"))
        parts = [Layout(Group(heading, grid))]
        if header_rows:
            parts.insert(0, Layout(header, size=header_rows))
        if footer_rows:
            parts.append(Layout(footer, size=footer_rows))
        layout = Layout()
        layout.split_column(*parts)
        return layout

    def _dispatched(self, count: int) -> int:
        """Return how many agents have their todos by now; all of them by 3/4 of the plan."""
        window = PLAN_SECONDS * _PLAN_DISPATCH_SHARE
        return min(count, int(self._elapsed / window * count))


class WorkStage(ScreenStage):
    """The agents work until they converge or you type "ship it"."""

    mode = "running"

    @override
    def start(self) -> None:
        """Forget which questions were asked and listen for answers.

        Also resets the prompt stash and the key-grace timers.
        """
        self._asked: set[str] = set()
        self._opened_at = 0.0
        self._answered_at = -math.inf
        self._stash = ""
        self._unsubscribe = self.wall.sim.events.subscribe(
            QuestionAnswered, self._on_answered
        )

    @override
    def finish(self, next_stage: str | None = None) -> None:
        """End the stage and stop listening for answers.

        Args:
            next_stage: The name to return, or ``None`` for the next in flow.
        """
        self._unsubscribe()
        super().finish(next_stage)

    def _on_answered(self, event: QuestionAnswered) -> None:
        self.session.flags.update(event.option.sets)
        wall = self.wall
        wall.question_cursor = 0
        wall.buffer = self._stash
        self._stash = ""
        self._answered_at = wall.sim.now

    @override
    def on_key(self, key: str) -> bool:
        """Answer the open question with the key, or handle it as usual.

        Args:
            key: A key name.

        Returns:
            ``False`` once the stage is done.
        """
        sim = self.wall.sim
        asked = sim.open_question
        if asked is None:
            # The esc that answered a question must not also dismiss the agents.
            if key == "esc" and sim.now - self._answered_at < _KEY_GRACE:
                return not self.is_done
            return super().on_key(key)
        if sim.now - self._opened_at < _KEY_GRACE:
            return not self.is_done
        question = asked[1]
        count = len(question.options)
        wall = self.wall
        if key in {"1", "2", "3", "4"} and int(key) <= count:
            self._answer(int(key) - 1)
        elif key == "up":
            wall.question_cursor = max(0, wall.question_cursor - 1)
        elif key == "down":
            wall.question_cursor = min(count - 1, wall.question_cursor + 1)
        elif key == "enter":
            self._answer(wall.question_cursor)
        elif key == "esc":
            self._answer(question.recommended)
        return not self.is_done

    def _answer(self, index: int) -> None:
        self.wall.sim.answer(index)

    def _is_pinned(self, question: Question) -> bool:
        pinned = self.session.pinned
        return any(key in pinned for option in question.options for key in option.sets)

    def _next_question(self) -> Question | None:
        flags = self.session.flags
        seen: set[str] = set()
        for scenario in self.wall.sim.scenarios:
            for question in scenario.questions:
                if question.key in seen:
                    continue
                seen.add(question.key)
                if (
                    question.key not in self._asked
                    and not self._is_pinned(question)
                    and self.wall.sim.now >= question.at * self.wall.sim.length
                    and all(flags.get(k) == v for k, v in question.when.items())
                ):
                    return question
        return None

    def _ask_next(self) -> None:
        sim = self.wall.sim
        question = self._next_question()
        running = [agent for agent in sim.agents if not agent.is_done]
        if question is None or not running:
            return
        self._asked.add(question.key)
        self._opened_at = sim.now
        self.wall.question_cursor = question.recommended
        self._stash, self.wall.buffer = self.wall.buffer, ""
        sim.ask(self.session.rng.choice(running), question)

    @override
    def update(self) -> None:
        """Ask and answer questions; move on once the swarm converges; ship once demo mode's time is up."""
        sim = self.wall.sim
        asked = sim.open_question
        if asked is not None:
            if (
                self.session.auto is not None
                and sim.now - self._opened_at >= _AUTO_ANSWER_DELAY
            ):
                self._answer(asked[1].recommended)
            return
        if sim.is_converged:
            done = f"all {len(sim.agents)} agents done. ready to ship."
            sim.report(sim.orchestrator, done)
            self.finish("ready")
            return
        self._ask_next()
        auto = self.session.auto
        if sim.open_question is None and auto is not None and sim.now >= auto:
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
        elif session.app is not None:
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
        elif session.app is not None:
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
