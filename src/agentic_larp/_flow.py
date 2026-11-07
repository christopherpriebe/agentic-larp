"""The flow: a session walks through named stages, built-in or plugged in."""

import importlib.metadata
import random
import re
import sys
from collections.abc import Callable, Mapping, Sequence
from contextlib import ExitStack
from dataclasses import dataclass, field
from typing import ClassVar, Protocol

from rich.console import Console, RenderableType
from rich.live import Live

from agentic_larp._errors import LarpError
from agentic_larp._grid import Grid
from agentic_larp._keys import Keys, KeySource
from agentic_larp._sim import Sim
from agentic_larp._wall import Mode, Wall
from agentic_larp.apps._base import AppContext, Outcome, Screen, run_frames

if sys.version_info >= (3, 12):
    pass
else:
    pass

FLOW: tuple[str, ...] = ("work", "wrap", "ready", "ship", "launch", "receipt")
END = "end"
STAGE_ENTRY_POINT_GROUP = "agentic_larp.stages"
_SHIP_WORDS = re.compile(r"\b(ship|send|yolo|lgtm|merge|deploy|push)", re.IGNORECASE)
_QUIT_WORDS = frozenset({"q", "quit", "exit", ":q"})
_SPAWN_WORDS = frozenset({"spawn", "more", "more agents", "scale"})


class _Replay:
    """A key source that holds back the keys the screen has not consumed."""

    def __init__(self, source: KeySource, pending: list[str]) -> None:
        self.source = source
        self.pending = pending

    def read(self) -> list[str]:
        self.pending.extend(self.source.read())
        return list(self.pending)


class _Consuming:
    """A screen that marks each key consumed before handing it over."""

    def __init__(self, screen: Screen, replay: _Replay) -> None:
        self.screen = screen
        self.replay = replay

    def render(self) -> RenderableType:
        return self.screen.render()

    def on_key(self, key: str) -> bool:
        self.replay.pending.pop(0)
        return self.screen.on_key(key)

    def tick(self, dt: float) -> bool:
        return self.screen.tick(dt)


@dataclass(slots=True)
class Session:
    """Everything the stages of one run share.

    Attributes:
        console: Where to draw and print.
        task: What the agents "build".
        sim: The swarm, or ``None`` when the run has no agents.
        rng: Randomness for stages that need it.
        app: Name of the payoff app to launch, or ``"none"``.
        then: Shell command to run instead of an app, or ``None``.
        auto: Demo mode: ship by itself after this many seconds, or never.
        fps: Frames per second.
        keys: Key source to read from; ``None`` reads the real keyboard.
        grid: Fixed feed grid with spotlight rotation, or ``None``.
        pace: Fast-forward for tests and demos.
        outcome: Whether the app should end well or melt down.
        flags: Free-form state for plugin stages.
        exit_code: The process exit code the run ends with.
        wall: The agent wall; the first wall stage creates it and the later
            ones share it.
    """

    console: Console
    task: str
    sim: Sim | None
    rng: random.Random
    app: str = "none"
    then: str | None = None
    auto: float | None = None
    fps: int = 20
    keys: KeySource | None = None
    grid: Grid | None = None
    pace: float = 1.0
    outcome: Outcome = Outcome.SUCCESS
    flags: dict[str, str] = field(default_factory=dict)
    exit_code: int = 0
    wall: Wall | None = None
    _stack: ExitStack | None = field(default=None, init=False, repr=False)
    _live: Live | None = field(default=None, init=False, repr=False)
    _source: KeySource | None = field(default=None, init=False, repr=False)
    _pending: list[str] = field(default_factory=list, init=False, repr=False)

    def app_context(self) -> AppContext:
        """Build the context a payoff app launches with.

        Returns:
            The console, task, auto, fps, keys and outcome of this session.
        """
        return AppContext(
            console=self.console,
            task=self.task,
            auto=self.auto,
            fps=self.fps,
            keys=self.keys,
            outcome=self.outcome,
        )

    def release_screen(self) -> None:
        """Close the shared full-screen display, if open.

        A stage calls this before it prints or hands the terminal to an app.
        """
        stack, self._stack = self._stack, None
        self._live = None
        self._source = None
        if stack is not None:
            stack.close()

    def _open_screen(
        self, first: RenderableType
    ) -> tuple[_Replay, Callable[[RenderableType], None]]:
        if self._live is None or self._source is None:
            with ExitStack() as stack:
                source = self.keys or Keys()
                if isinstance(source, Keys):
                    stack.enter_context(source)
                live = Live(
                    first,
                    console=self.console,
                    screen=True,
                    auto_refresh=False,
                    transient=True,
                )
                stack.enter_context(live)
                self._stack = stack.pop_all()
            self._live, self._source = live, source
        live = self._live

        def update(frame: RenderableType) -> None:
            live.update(frame, refresh=True)

        update(first)
        return _Replay(self._source, self._pending), update


class Stage(Protocol):
    """One step of the flow."""

    def run(self, session: Session) -> str | None:
        """Play the stage.

        Args:
            session: The state shared by every stage.

        Returns:
            ``None`` for the next stage in the flow; a registered stage name to
            jump there (the flow resumes after the first occurrence of that
            name in the flow; a stage outside the flow ends the session unless
            it returns a name); :data:`END` to finish.
        """
        ...


def run_screen(session: Session, screen: Screen) -> None:
    """Drive a screen full screen until it returns ``False``.

    Consecutive calls share one display, so changing stage does not flicker.
    Keys read after the one that ended the screen wait for the next call.
    Call :meth:`Session.release_screen` to close it.

    Args:
        session: Supplies the key source, the frame rate and the display.
        screen: The screen to draw and feed keys to.
    """
    replay, update = session._open_screen(screen.render())  # noqa: SLF001 - the display is the session's own state; this is its driver
    run_frames(_Consuming(screen, replay), replay, session.fps, update)


class ScreenStage:
    """A stage that shows the agent wall and reads the prompt.

    Subclasses set :attr:`mode` and override the hooks they care about.

    Attributes:
        session: The session, once begun.
        wall: The shared wall, once begun.
        is_done: Whether the stage has finished.
        next_stage: What the stage returns when it ends.
    """

    mode: ClassVar[Mode] = "running"
    session: Session
    wall: Wall

    def __init__(self) -> None:
        self.is_done = False
        self.next_stage: str | None = None

    def begin(self, session: Session) -> None:
        """Attach to the session and dress the wall for this stage.

        Args:
            session: The session to run in.

        Raises:
            LarpError: If the session has no swarm to show.
        """
        if session.sim is None:
            message = f"the {type(self).__name__} needs a swarm, and this run has none"
            raise LarpError(message)
        self.session = session
        if session.wall is None:
            session.wall = Wall(
                session.sim, session.console, grid=session.grid, pace=session.pace
            )
        self.wall = session.wall
        self.wall.set_mode(self.mode)
        self.start()

    def start(self) -> None:
        """Hook: run once when the stage begins."""

    def update(self) -> None:
        """Hook: run once per frame after the wall steps."""

    def finish(self, next_stage: str | None = None) -> None:
        """End the stage.

        Args:
            next_stage: The name to return, or ``None`` for the next in flow.
        """
        self.is_done = True
        self.next_stage = next_stage

    def on_key(self, key: str) -> bool:
        """Handle a keypress.

        Args:
            key: A key name from :func:`agentic_larp.parse_keys`.

        Returns:
            ``False`` once the stage is done.
        """
        text = self.wall.handle_key(key)
        if text is not None:
            self.submit(text)
        return not self.is_done

    def tick(self, dt: float) -> bool:
        """Advance the wall and the stage by one frame.

        Args:
            dt: Real seconds since the previous frame.

        Returns:
            ``False`` once the stage is done.
        """
        self.wall.step(dt)
        if not self.is_done:
            self.update()
        return not self.is_done

    def render(self) -> RenderableType:
        """Build the current frame.

        Returns:
            The wall.
        """
        return self.wall.render()

    def submit(self, text: str) -> None:
        """Act on a line the user submitted.

        Args:
            text: The line, already stripped; empty for a bare enter.
        """
        if not text:
            self.on_empty()
        elif text.lower() in _QUIT_WORDS:
            self.finish("abandon")
        elif _SHIP_WORDS.search(text):
            self.on_ship(text)
        elif text.lower() in _SPAWN_WORDS:
            self.on_spawn()
        else:
            self.on_text(text)

    def on_empty(self) -> None:
        """Hook: a bare enter."""

    def on_ship(self, text: str) -> None:
        """Hook: a line that says to ship.

        Args:
            text: The line.
        """

    def on_spawn(self) -> None:
        """Hook: a request for more agents; refused by default."""
        sim = self.wall.sim
        sim.reports.append((sim.orchestrator, "no new agents while wrapping up."))

    def on_text(self, text: str) -> None:
        """Hook: any other line; broadcast to the agents by default.

        Args:
            text: The line.
        """
        self.wall.sim.broadcast(text)

    def run(self, session: Session) -> str | None:
        """Play the stage on the shared display.

        Args:
            session: The session to run in.

        Returns:
            :attr:`next_stage`.

        Raises:
            LarpError: If the session has no swarm to show.
        """  # noqa: DOC502 - the error comes from a helper this calls; callers still need to know
        self.begin(session)
        run_screen(session, self)
        return self.next_stage


def stage_registry() -> dict[str, Callable[[], Stage]]:
    """Return every stage by name: the built-ins, then installed plugins.

    Plugins register under the ``agentic_larp.stages`` entry-point group. A
    plugin with a built-in's name replaces it.

    Returns:
        Stage name mapped to a factory that builds the stage.
    """
    from agentic_larp import _stages  # noqa: PLC0415 - the stages import this module

    registry: dict[str, Callable[[], Stage]] = {
        "work": _stages.WorkStage,
        "wrap": _stages.WrapStage,
        "ready": _stages.ReadyStage,
        "ship": _stages.ShipStage,
        "launch": _stages.LaunchStage,
        "receipt": _stages.ReceiptStage,
        "abandon": _stages.AbandonStage,
    }
    for entry_point in importlib.metadata.entry_points(group=STAGE_ENTRY_POINT_GROUP):
        if entry_point.name != END:
            registry[entry_point.name] = entry_point.load()
    return registry


def _look_up(
    registry: Mapping[str, Callable[[], Stage]], name: str
) -> Callable[[], Stage]:
    factory = registry.get(name)
    if factory is None:
        message = f"no stage called {name!r}; try: {', '.join(registry)}"
        raise LarpError(message)
    return factory


def run_flow(
    session: Session,
    flow: Sequence[str] = FLOW,
    stages: Mapping[str, Callable[[], Stage]] | None = None,
) -> int:
    """Play the stages of a flow in order.

    A jump resumes the flow after the first occurrence of that name; a jump
    to a stage outside the flow ends the session unless that stage returns a
    name. The screen is released before any stage that is not a
    :class:`ScreenStage`, and at the end.

    Args:
        session: The state shared by every stage.
        flow: Stage names, in order.
        stages: Stage factories by name; defaults to :func:`stage_registry`.

    Returns:
        The session's exit code.

    Raises:
        LarpError: If the flow or a jump names an unregistered stage.
    """  # noqa: DOC502 - the error comes from a helper this calls; callers still need to know
    registry = stage_registry() if stages is None else stages
    for name in flow:
        _look_up(registry, name)
    name: str | None = flow[0] if flow else None
    index: int | None = 0
    try:
        while name is not None and name != END:
            stage = _look_up(registry, name)()
            if not isinstance(stage, ScreenStage):
                session.release_screen()
            result = stage.run(session)
            if result is not None:
                name = result
                index = flow.index(result) if result in flow else None
            elif index is None or index + 1 >= len(flow):
                name = None
            else:
                index += 1
                name = flow[index]
    finally:
        session.release_screen()
    return session.exit_code
