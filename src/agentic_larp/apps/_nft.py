"""An NFT mint: a pixel ape appearing row by row, one jpeg at a time."""

import random
from collections import deque

from rich.align import Align
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.text import Text

from agentic_larp.apps._base import AppContext
from agentic_larp.apps._flow import BREAK_AT, BREAK_SECONDS, push_feed
from agentic_larp.meltdown import Meltdown, is_doomed, play

BORDER = "#3a4a5a"
APE = (
    "      ▄▄▄▄▄▄▄▄▄▄▄▄      ",
    "    ▄██████████████▄    ",
    "  ▄████▀▀▀▀▀▀▀▀▀▀████▄  ",
    " ▐███▀  ▄▄▄  ▄▄▄  ▀███▌ ",
    " ▐███  █▀◉▀██▀◉▀█  ███▌ ",
    "  ████  ▀▀▀▄▄▄▀▀▀  ████ ",
    "  ▀███▄    ▀▀▀    ▄███▀ ",
    "   ▀████▄▄ ▄▄▄ ▄▄████▀  ",
    "     ▀▀████████████▀▀   ",
    "   ▄▄████████████████▄▄ ",
    "  ████▀▀██████████▀▀████",
    "  ▀▀▀    ████████    ▀▀▀",
)
FAIL_ERRORS = (
    "right-click → save as: 4,000,000 times",
    "floor price: 0.0000 ETH",
    "the ape was a png all along",
    "OpenSea: collection delisted",
    "ipfs: 1 peer (your laptop, now offline)",
)
MELTDOWN = Meltdown(errors=FAIL_ERRORS, reveal="jk. you still own the right-click.")
HYPE = (
    "💬 discord: gm",
    "💬 discord: gm gm",
    "💬 discord: wen reveal",
    "💬 discord: utility is coming (it is not)",
    "💬 discord: floor looking strong, ser",
)
_SUPPLY = 10_000
_MINT_SECONDS = 20.0  # no-key time to mint the whole collection
_START_FLOOR = 0.05
_FLOOR_PER_MINT = 0.0004
_FEED_LENGTH = 6
_PUSH_DECAY = 3.0
_MAX_PUSH = 8.0
_KEY_MINT = 0.01
_FAIL_LINES = (
    "someone right-clicked → save as",
    "screenshot is going viral",
    "floor dropping",
    "OpenSea delisted the collection",
)


class NftScreen:
    """A mint counter, a floor price, and an ape that is mostly gas."""

    def __init__(self, context: AppContext, rng: random.Random | None = None) -> None:
        self.context = context
        self.doomed = is_doomed(context)
        self.rng = rng or context.rng
        self.clock = 0.0
        self.progress = 0.0
        self.floor = _START_FLOOR
        self.gas = 180
        self.feed: deque[tuple[str, str]] = deque(maxlen=_FEED_LENGTH)
        self.broken_at: float | None = None
        self.next_line = 0.0
        self.fail_lines = list(_FAIL_LINES)
        self.saves = 0

    @property
    def has_broken(self) -> bool:
        """Return whether someone has right-clicked the ape."""
        return self.broken_at is not None

    @property
    def minted(self) -> int:
        """Return how many of the ten thousand are minted."""
        return int(min(1.0, self.progress) * _SUPPLY)

    def on_key(self, key: str) -> bool:
        """Mint faster, or leave.

        Args:
            key: A key name.

        Returns:
            ``False`` on escape.
        """
        if key == "esc":
            return False
        if not self.has_broken:
            self.progress += _KEY_MINT
        return True

    def tick(self, dt: float) -> bool:
        """Mint, move the floor, and (when failing) lose the floor.

        Args:
            dt: Real seconds since the last frame.

        Returns:
            ``False`` once a failing mint has finished collapsing.
        """
        self.clock += dt
        if self.doomed and self.broken_at is None and self.clock >= BREAK_AT:
            self.broken_at = self.next_line = self.clock
        if self.broken_at is not None:
            self.floor *= max(0.0, 1 - dt * 1.5)
            self.saves += int(self.rng.random() * 400_000 * dt) + 1
            if self.clock >= self.next_line and self.fail_lines:
                self.next_line = self.clock + BREAK_SECONDS / len(_FAIL_LINES)
                push_feed(self.feed, "bold red", f"🖱  {self.fail_lines.pop(0)}")
            return self.clock - self.broken_at < BREAK_SECONDS
        self.progress = min(1.0, self.progress + dt / _MINT_SECONDS)
        self.floor = _START_FLOOR + self.minted * _FLOOR_PER_MINT
        self.gas = max(20, self.gas + self.rng.randint(-15, 15))
        if self.rng.random() < dt * 2:
            push_feed(self.feed, "magenta", self.rng.choice(HYPE))
        return True

    def render(self) -> RenderableType:
        """Draw the ape, the mint counter, floor, gas, and Discord.

        Returns:
            The frame.
        """
        rows = len(APE)
        shown = rows if self.has_broken else int(min(1.0, self.progress) * rows) + 1
        art = [
            row if index < shown else " " * len(row) for index, row in enumerate(APE)
        ]
        style = "red" if self.has_broken else "yellow"
        ape = Panel(
            Align.center(Text("\n".join(art), style=style)),
            title=Text(f"🖼  {self.context.task}"),
            title_align="left",
            border_style="red" if self.has_broken else BORDER,
        )
        stats = Text.assemble(
            (f"minted {self.minted:,}/{_SUPPLY:,}", "bold"),
            (
                f"   floor {self.floor:.4f} ETH",
                "bold green" if not self.has_broken else "bold red",
            ),
            (f"   gas {self.gas} gwei", "dim"),
        )
        feed = Text("\n").join(Text(line, style=style) for style, line in self.feed)
        parts: list[RenderableType] = [ape, stats, feed]
        if self.has_broken:
            parts.append(
                Text(f"right-click → save as: {self.saves:,} times", style="bold red")
            )
        parts.append(Text("any key: mint faster · esc: paper hands", style="dim"))
        return Group(*parts)


def run(context: AppContext) -> None:
    """Mint the collection.

    Args:
        context: The app's context.
    """
    play(
        context,
        NftScreen(context),
        MELTDOWN,
        success="🖼 minted out. floor price 4.20 ETH. you own a jpeg now.",
        failure="it's a jpeg of a monkey. it was always a jpeg of a monkey.",
    )
