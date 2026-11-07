"""The shared meltdown: glitch-decay, an error cascade, a fake death, then "jk"."""

import math
import random
from collections.abc import Sequence
from dataclasses import replace
from io import StringIO

from rich.align import Align
from rich.console import Console, RenderableType
from rich.text import Text

from agentic_larp.apps._base import AppContext, run_loop

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
_DECAY_SECONDS = 2.5
_CASCADE_SECONDS = 4.0
_DEATH_SECONDS = 2.0
_REVEAL_SECONDS = 1.0
_SKIP_REVEAL_SECONDS = 0.4
_CASCADE_SPREAD = 0.85  # share of the cascade phase spent revealing lines
_SHARED_SAMPLE = 10
_COLOR_MAX = 255
_REVEAL = "jk. it's fine. [exit 0]"

_EXIT_137 = ("", "", "[process exited with code 137]")
_KERNEL_PANIC = (
    "Kernel panic - not syncing: VFS: Unable to mount root fs on unknown-block(0,0)",
    "CPU: 0 PID: 1 Comm: swapper/0 Not tainted 6.9.0-vibes #1",
    "Call Trace:",
    " dump_stack+0x6d/0x8b",
    " panic+0x101/0x2e3",
    " mount_block_root+0x2a8/0x2b3",
    " prepare_namespace+0x136/0x16c",
    "---[ end Kernel panic - not syncing: ship it on a friday ]---",
)
_BLUE_SCREEN = (
    ":(",
    "",
    "Your PC ran into a problem and needs to restart.",
    "We're just collecting some error info, and then we'll restart for you.",
    "",
    "42% complete",
    "",
    "Stop code: INTERN_HAS_ROOT",
)
_DEATHS = (
    (_EXIT_137, "white on black"),
    (_KERNEL_PANIC, "white on black"),
    (_BLUE_SCREEN, "white on #0078d7"),
)


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


class _Meltdown:
    def __init__(
        self, lines: list[str], errors: Sequence[str], rng: random.Random
    ) -> None:
        self.lines = lines
        self.plan = _plan(lines, random.Random(rng.randrange(2**32)))
        shared = rng.sample(SHARED_ERRORS, _SHARED_SAMPLE)
        self.cascade = [*errors, *shared]
        rng.shuffle(self.cascade)
        screen, self.death_style = rng.choice(_DEATHS)
        self.death = "\n".join(screen)
        self.clock = 0.0
        self.end = _DECAY_SECONDS + _CASCADE_SECONDS + _DEATH_SECONDS + _REVEAL_SECONDS

    @property
    def reveal_at(self) -> float:
        return _DECAY_SECONDS + _CASCADE_SECONDS + _DEATH_SECONDS

    def on_key(self, key: str) -> bool:
        if key != "esc":
            return True
        if self.clock >= self.reveal_at:
            return False
        self.clock = self.reveal_at
        self.end = self.clock + _SKIP_REVEAL_SECONDS
        return True

    def tick(self, dt: float) -> bool:
        self.clock += dt
        return self.clock < self.end

    def render(self) -> RenderableType:
        clock = self.clock
        if clock < _DECAY_SECONDS:
            return self._render_decay(clock / _DECAY_SECONDS)
        clock -= _DECAY_SECONDS
        if clock < _CASCADE_SECONDS:
            return self._render_cascade(clock / _CASCADE_SECONDS)
        if clock - _CASCADE_SECONDS < _DEATH_SECONDS:
            return Align(
                Text(self.death, style=self.death_style, no_wrap=True),
                align="left",
                vertical="top",
                style=self.death_style,
            )
        reveal = Text(_REVEAL, style="bold green")
        note = Text("(nothing was harmed. the agents are fine. mostly.)", style="dim")
        return Align.center(Text("\n").join([reveal, note]), vertical="middle")

    def _render_decay(self, amount: float) -> RenderableType:
        glitched = _apply(self.lines, self.plan, amount)
        fade = int(_COLOR_MAX * (1 - amount))
        return Text(
            "\n".join(glitched),
            style=f"bold rgb({_COLOR_MAX},{fade},{fade})",
            no_wrap=True,
        )

    def _render_cascade(self, fraction: float) -> RenderableType:
        count = int(fraction / _CASCADE_SPREAD * len(self.cascade)) + 1
        shown = self.cascade[: min(count, len(self.cascade))]
        height = len(self.lines)
        rows = [
            Text(f"[{index * 0.37:8.3f}] ERROR {error}", style="bold red", no_wrap=True)
            for index, error in enumerate(shown)
        ]
        return Text("\n").join(rows[-height:])


def run_meltdown(
    context: AppContext,
    frame: RenderableType,
    errors: Sequence[str],
    rng: random.Random | None = None,
) -> None:
    """Melt a frame down: decay, error cascade, fake death, then "jk".

    Runs its full length whatever ``context.auto`` says; escape skips ahead.
    The reveal line is printed again once the screen closes, so it stays in
    the scrollback.

    Args:
        context: The app's context.
        frame: The last frame the app drew.
        errors: App-flavored errors for the cascade, mixed with
            :data:`SHARED_ERRORS`.
        rng: Random source.
    """
    rng = rng or random.Random()
    lines = capture_frame(context.console, frame)
    run_loop(replace(context, auto=None), _Meltdown(lines, errors, rng))
    context.console.print(Text(_REVEAL, style="bold green"))
