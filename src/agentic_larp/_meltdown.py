"""The meltdown library: decay, an error cascade, a fake death, then "jk".

Every app builds its own :class:`Meltdown` and plays it with :func:`play` or
:func:`run_meltdown`. An app melts down only when the ``ending`` session flag
is ``meltdown``; there is no chance involved.
"""

import math
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from io import StringIO
from typing import Protocol

from rich.align import Align
from rich.console import Console, RenderableType
from rich.text import Text

from agentic_larp._errors import LarpError
from agentic_larp.apps._base import AppContext, Screen, run_loop

ENDING_FLAG = "ending"
MELTDOWN_ENDING = "meltdown"
SUCCESS_ENDING = "success"

SHARED_ERRORS = (
    "rm -rf / --no-preserve-root ... ok",
    "Deleting C:\\Windows\\System32\\ (37%)",
    "kernel panic: not syncing: vibes exhausted",
    "segfault in vibes.so",
    "npm ERR! peer dep conflict with reality",
    "FATAL: out of tokens",
    "git push --force: rejected by physics",
    "OutOfMemoryError: the agents ate it all",
    "stack overflow: the real one, on the internet",
    "TypeError: undefined is not a girlfriend",
    "disk full: 40 TB of node_modules",
    "ERROR: the intern has root",
    "SIGSEGV: segmentation vibes",
    "AssertionError: assert True is False",
    "panic: unreachable code reached",
    "cloud provider: your card was declined by the universe",
    "ENOENT: no such reality",
    "fatal: refusing to merge unrelated feelings",
)

_GLYPHS = "▓▒░█#@%&$*!?/\\|<>~^"
_REVEAL_SECONDS = 1.0
_SKIP_REVEAL_SECONDS = 0.4
_CASCADE_SPREAD = 0.85  # share of the cascade phase spent revealing lines
_COLOR_MAX = 255
_DEFAULT_REVEAL = "jk. it's fine. [exit 0]"


@dataclass(frozen=True, slots=True)
class DeathScreen:
    """A fake death screen.

    Attributes:
        lines: The text of the screen, one string per row.
        style: Rich style for the whole screen.
    """

    lines: tuple[str, ...]
    style: str


EXIT_137 = DeathScreen(("", "", "[process exited with code 137]"), "white on black")
KERNEL_PANIC = DeathScreen(
    (
        "Kernel panic - not syncing: VFS: Unable to mount root fs on unknown-block(0,0)",
        "CPU: 0 PID: 1 Comm: swapper/0 Not tainted 6.9.0-vibes #1",
        "Call Trace:",
        " dump_stack+0x6d/0x8b",
        " panic+0x101/0x2e3",
        " mount_block_root+0x2a8/0x2b3",
        " prepare_namespace+0x136/0x16c",
        "---[ end Kernel panic - not syncing: ship it on a friday ]---",
    ),
    "white on black",
)
BLUE_SCREEN = DeathScreen(
    (
        ":(",
        "",
        "Your PC ran into a problem and needs to restart.",
        "We're just collecting some error info, and then we'll restart for you.",
        "",
        "42% complete",
        "",
        "Stop code: INTERN_HAS_ROOT",
    ),
    "white on #0078d7",
)
DEATHS = (EXIT_137, KERNEL_PANIC, BLUE_SCREEN)


@dataclass(frozen=True, slots=True)
class Meltdown:
    """One app's custom meltdown.

    Attributes:
        errors: App-flavored errors for the cascade.
        shared: How many random :data:`SHARED_ERRORS` to mix in.
        deaths: Fake death screens; one is drawn at random.
        reveal: The "jk" line shown at the end and left in the scrollback.
        note: A dim line under the reveal.
        decay_seconds: Length of the glitch-decay phase.
        cascade_seconds: Length of the error-cascade phase.
        death_seconds: Length of the fake-death phase.

    Raises:
        LarpError: If a phase length is negative or not finite, ``shared`` is
            outside 0 to ``len(SHARED_ERRORS)``, or ``deaths`` is empty.
    """

    errors: tuple[str, ...] = ()
    shared: int = 10
    deaths: tuple[DeathScreen, ...] = DEATHS
    reveal: str = _DEFAULT_REVEAL
    note: str = "(nothing was harmed. the agents are fine. mostly.)"
    decay_seconds: float = 2.5
    cascade_seconds: float = 4.0
    death_seconds: float = 2.0

    def __post_init__(self) -> None:
        for name, label in (
            ("decay_seconds", "decay"),
            ("cascade_seconds", "cascade"),
            ("death_seconds", "death"),
        ):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0:
                message = (
                    f"{label} phase must be a finite number of seconds, not {value}"
                )
                raise LarpError(message)
        if (
            not isinstance(self.shared, int)
            or isinstance(self.shared, bool)
            or not 0 <= self.shared <= len(SHARED_ERRORS)
        ):
            message = (
                f"shared must be an int between 0 and {len(SHARED_ERRORS)}, "
                f"not {self.shared!r}"
            )
            raise LarpError(message)
        if not self.deaths:
            message = "a meltdown needs at least one death screen"
            raise LarpError(message)
        if not all(isinstance(death, DeathScreen) for death in self.deaths):
            message = "every death screen must be a DeathScreen"
            raise LarpError(message)


def _plan(lines: Sequence[str], rng: random.Random) -> list[list[tuple[float, str]]]:
    # Draw a fixed threshold and glyph for every cell, in a stable order.
    plan: list[list[tuple[float, str]]] = []
    for line in lines:
        row: list[tuple[float, str]] = []
        for char in line:
            if char == " ":
                row.append((math.inf, char))
            else:
                row.append((rng.random(), rng.choice(_GLYPHS)))
        plan.append(row)
    return plan


def _apply(
    lines: Sequence[str], plan: list[list[tuple[float, str]]], amount: float
) -> list[str]:
    return [
        "".join(
            glyph if threshold < amount else char
            for char, (threshold, glyph) in zip(line, row, strict=True)
        )
        for line, row in zip(lines, plan, strict=True)
    ]


def decay(lines: Sequence[str], amount: float, rng: random.Random) -> list[str]:
    """Corrupt a fraction of the visible characters into glitch glyphs.

    Each non-space position gets a fixed threshold and glyph in a stable
    order, so with the same seed a larger amount corrupts a superset.

    Args:
        lines: The frame, one string per row.
        amount: How much to corrupt, from 0 (nothing) to 1 (everything).
        rng: Random source for thresholds and glyphs.

    Returns:
        Lines of the same count and lengths, with spaces untouched.

    Raises:
        ValueError: If ``amount`` is outside 0 to 1.
    """
    if not 0 <= amount <= 1:
        message = f"amount must be between 0 and 1, not {amount}"
        raise ValueError(message)
    return _apply(lines, _plan(lines, rng), amount)


def capture_frame(console: Console, frame: RenderableType) -> list[str]:
    """Render a frame to plain text at the console's size.

    Args:
        console: Supplies the width and height.
        frame: Anything Rich can render.

    Returns:
        Exactly ``height`` lines, trailing spaces trimmed.
    """
    width, height = console.size
    buffer = StringIO()
    plain = Console(
        file=buffer,
        width=width,
        height=height,
        force_terminal=False,
        color_system=None,
        legacy_windows=False,
    )
    plain.print(frame, height=height)
    lines = [line.rstrip() for line in buffer.getvalue().split("\n")][:height]
    return lines + [""] * (height - len(lines))


class MeltdownScreen:
    """A screen that plays a :class:`Meltdown` over a captured frame.

    Args:
        lines: The captured frame, one string per row.
        meltdown: The meltdown to play.
        rng: Random source for the glitch, the cascade and the death screen.
    """

    def __init__(
        self, lines: Sequence[str], meltdown: Meltdown, rng: random.Random
    ) -> None:
        self._lines = list(lines)
        self._meltdown = meltdown
        self._plan = _plan(self._lines, random.Random(rng.randrange(2**32)))
        shared = rng.sample(SHARED_ERRORS, meltdown.shared)
        self._cascade = [*meltdown.errors, *shared]
        rng.shuffle(self._cascade)
        death = rng.choice(meltdown.deaths)
        self._death = "\n".join(death.lines)
        self._death_style = death.style
        self._clock = 0.0
        self._end = self.reveal_at + _REVEAL_SECONDS

    @property
    def reveal_at(self) -> float:
        """Return the moment the reveal starts."""
        meltdown = self._meltdown
        return (
            meltdown.decay_seconds + meltdown.cascade_seconds + meltdown.death_seconds
        )

    def on_key(self, key: str) -> bool:
        """Handle a keypress; escape skips to the reveal, then leaves.

        Args:
            key: The key pressed.

        Returns:
            ``False`` to exit.
        """
        if key != "esc":
            return True
        if self._clock >= self.reveal_at:
            return False
        self._clock = self.reveal_at
        self._end = self._clock + _SKIP_REVEAL_SECONDS
        return True

    def tick(self, dt: float) -> bool:
        """Advance the meltdown.

        Args:
            dt: Real seconds since the last tick.

        Returns:
            ``False`` once the reveal is over.
        """
        self._clock += dt
        return self._clock < self._end

    def render(self) -> RenderableType:
        """Build the current frame.

        Returns:
            The frame for the current phase.
        """
        meltdown = self._meltdown
        clock = self._clock
        if clock < meltdown.decay_seconds:
            return self._render_decay(clock / meltdown.decay_seconds)
        clock -= meltdown.decay_seconds
        if clock < meltdown.cascade_seconds:
            return self._render_cascade(clock / meltdown.cascade_seconds)
        if clock - meltdown.cascade_seconds < meltdown.death_seconds:
            return Align(
                Text(self._death, style=self._death_style, no_wrap=True),
                align="left",
                vertical="top",
                style=self._death_style,
            )
        reveal = Text(meltdown.reveal, style="bold green")
        note = Text(meltdown.note, style="dim")
        return Align.center(Text("\n").join([reveal, note]), vertical="middle")

    def _render_decay(self, amount: float) -> RenderableType:
        glitched = _apply(self._lines, self._plan, amount)
        fade = int(_COLOR_MAX * (1 - amount))
        return Text(
            "\n".join(glitched),
            style=f"bold rgb({_COLOR_MAX},{fade},{fade})",
            no_wrap=True,
        )

    def _render_cascade(self, fraction: float) -> RenderableType:
        count = int(fraction / _CASCADE_SPREAD * len(self._cascade)) + 1
        shown = self._cascade[: min(count, len(self._cascade))]
        height = len(self._lines)
        rows = [
            Text(f"[{index * 0.37:8.3f}] ERROR {error}", style="bold red", no_wrap=True)
            for index, error in enumerate(shown)
        ]
        return Text("\n").join(rows[-height:])


def run_meltdown(
    context: AppContext, frame: RenderableType, meltdown: Meltdown
) -> None:
    """Melt a frame down: decay, error cascade, fake death, then "jk".

    Runs its full length whatever ``context.auto`` says; escape skips ahead.
    The reveal line is printed again once the screen closes, so it stays in
    the scrollback.

    Args:
        context: The app's context; its ``rng`` drives the randomness.
        frame: The last frame the app drew.
        meltdown: The app's meltdown.
    """
    lines = capture_frame(context.console, frame)
    run_loop(replace(context, auto=None), MeltdownScreen(lines, meltdown, context.rng))
    context.console.print(Text(meltdown.reveal))


def _describe_unknown_ending(ending: str) -> str:
    return f"unknown ending {ending!r}; use {MELTDOWN_ENDING} or {SUCCESS_ENDING}"


def check_ending(flags: Mapping[str, str]) -> None:
    """Check that the ``ending`` flag, if set, is a known ending.

    Args:
        flags: The session flags.

    Raises:
        LarpError: If the ending is neither ``meltdown`` nor ``success``.
    """
    ending = flags.get(ENDING_FLAG)
    if ending is not None and ending not in {MELTDOWN_ENDING, SUCCESS_ENDING}:
        message = _describe_unknown_ending(ending)
        raise LarpError(message)


def is_doomed(context: AppContext) -> bool:
    """Return whether the app should break and melt down.

    Args:
        context: The app's context.

    Returns:
        ``True`` when the ``ending`` flag is ``meltdown``. An unknown ending
        raises ``LarpError`` (see :func:`check_ending`).
    """
    check_ending(context.flags)
    return context.flags.get(ENDING_FLAG) == MELTDOWN_ENDING


class BreakableScreen(Screen, Protocol):
    """A screen that knows whether it broke."""

    @property
    def has_broken(self) -> bool:
        """Return whether the failure beat has started."""
        ...


def play(
    context: AppContext,
    screen: BreakableScreen,
    meltdown: Meltdown,
    *,
    success: str,
    failure: str,
) -> None:
    """Run a screen, then melt down if it broke, else say the normal goodbye.

    When the app is doomed ``auto`` is dropped, or demo mode would end the app
    before it breaks.

    Args:
        context: The app's context.
        screen: The app's screen.
        meltdown: The app's meltdown.
        success: Goodbye line when the app did not break.
        failure: Goodbye line printed after the meltdown.
    """
    doomed = is_doomed(context)
    run_loop(replace(context, auto=None) if doomed else context, screen)
    if screen.has_broken:
        run_meltdown(context, screen.render(), meltdown)
        context.console.print(failure)
    else:
        context.console.print(success)
