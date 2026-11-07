"""One podcast chopped into 900+ clips, all of them the same idea."""

import random
from collections import deque

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.text import Text

from agentic_larp.apps._base import AppContext
from agentic_larp.apps._flow import BREAK_AT, BREAK_SECONDS, push_feed
from agentic_larp.meltdown import Meltdown, is_doomed, play

BORDER = "#3a4a5a"
SOURCE = "3h14m podcast · topic: 'mindset'"
GUEST = "guest: 'founder' (of the podcast)"
CAPTION_STYLE = "ONE WORD AT A TIME 🔥"
RATE = "rate: $1 per 1,000 views"
CRAZY = "that's crazy bro"
THUMBNAILS = "░▒▓▚▞▖▗"
NOISE = "▀▄▌▐░▒▓█╳#@%&?"
FAIL_ERRORS = (
    f"ERR: every clip is '{CRAZY}'",
    "FATAL: duplicate content detected ×912",
    "PANIC: subtitles achieved 100% caps, ran out of caps",
    "clippers online: 40,000 (all clipping the same 4 seconds)",
    "unique ideas: 1 (still)",
)
MELTDOWN = Meltdown(errors=FAIL_ERRORS, reveal="jk. the full episode was 4 minutes.")
_MAX_CLIPS = 912
_CLIPS_PER_SECOND = 140.0
_PENDING_PER_CLIP = 0.40 / _MAX_CLIPS
_CLIPPERS = 40_000
_GRID_COLUMNS = 24
_GRID_ROWS = 4
_WAVE_WIDTH = 48
_WAVE_LEVELS = "▁▂▃▄▅▆▇█"
_FEED_LENGTH = 6
_PUSH_DECAY = 3.0
_MAX_PUSH = 8.0
_CAPTION_WORDS = ("so", "mindset", "is", "basically", "a", "mindset", "100%")
_CAPTION_INTERVAL = 0.5  # seconds between caption words
_FAIL_LINES = (
    f"every clip is now the same 4 seconds: '{CRAZY}'",
    f"'{CRAZY}' x912",
    "duplicate content detected",
    "the grid is just noise now",
    "link in bio (bio deleted)",
)


class ClipfarmScreen:
    """A grid of phones filling with clips of one idea."""

    def __init__(self, context: AppContext, rng: random.Random | None = None) -> None:
        self.context = context
        self.doomed = is_doomed(context)
        self.rng = rng or context.rng
        self.clock = 0.0
        self.push = 0.0
        self.clips = 0.0
        self.feed: deque[tuple[str, str]] = deque(maxlen=_FEED_LENGTH)
        self.broken_at: float | None = None
        self.next_line = 0.0
        self.next_caption = 0.0
        self.caption_index = 0
        self.fail_lines = list(_FAIL_LINES)

    @property
    def has_broken(self) -> bool:
        """Return whether every clip has become the same four seconds."""
        return self.broken_at is not None

    def on_key(self, key: str) -> bool:
        """Clip faster, or give up.

        Args:
            key: A key name.

        Returns:
            ``False`` on escape.
        """
        if key == "esc":
            return False
        self.push = min(_MAX_PUSH, self.push + 1.0)
        return True

    def tick(self, dt: float) -> bool:
        """Extract clips; when failing, they all collapse into one.

        Args:
            dt: Real seconds since the last frame.

        Returns:
            ``False`` once a failing farm has finished falling over.
        """
        self.clock += dt
        self.push = max(0.0, self.push - dt * _PUSH_DECAY)
        if self.doomed and self.broken_at is None and self.clock >= BREAK_AT:
            self.broken_at = self.next_line = self.clock
        if self.broken_at is not None:
            if self.clock >= self.next_line and self.fail_lines:
                self.next_line = self.clock + BREAK_SECONDS / len(_FAIL_LINES)
                push_feed(self.feed, "bold red", self.fail_lines.pop(0))
            return self.clock - self.broken_at < BREAK_SECONDS
        self.clips = min(
            float(_MAX_CLIPS), self.clips + dt * _CLIPS_PER_SECOND * (1 + self.push)
        )
        if self.clock >= self.next_caption:
            self.next_caption = self.clock + _CAPTION_INTERVAL
            word = _CAPTION_WORDS[self.caption_index % len(_CAPTION_WORDS)]
            self.caption_index += 1
            self.feed.append(("green", f"🔥 {word}"))
        return True

    def _grid(self) -> Text:
        total = _GRID_COLUMNS * _GRID_ROWS
        filled = int(self.clips / _MAX_CLIPS * total)
        lines: list[Text] = []
        for row in range(_GRID_ROWS):
            line = Text()
            for column in range(_GRID_COLUMNS):
                if self.has_broken:
                    line.append(f"[{self.rng.choice(NOISE)}]", style="red")
                elif row * _GRID_COLUMNS + column < filled:
                    line.append(f"[{self.rng.choice(THUMBNAILS)}]", style="cyan")
                else:
                    line.append("[ ]", style="dim")
            lines.append(line)
        return Text("\n").join(lines)

    def _wave(self) -> Text:
        if self.has_broken:
            return Text("█" * _WAVE_WIDTH, style="red")
        bars = "".join(self.rng.choice(_WAVE_LEVELS) for _ in range(_WAVE_WIDTH))
        return Text(bars, style="magenta")

    def render(self) -> RenderableType:
        """Draw the grid, waveform, counters, and caption feed.

        Returns:
            The frame.
        """
        clips = int(self.clips)
        pending = clips * _PENDING_PER_CLIP
        counters = Text("\n").join(
            [
                Text(f"clips extracted: {clips:,} · unique ideas: 1", style="bold"),
                Text(f"clippers online: {_CLIPPERS:,}"),
                Text(f"{RATE} · pending: ${pending:,.2f}"),
                Text(f"captions: {CAPTION_STYLE}"),
                Text(f"source: {SOURCE}", style="dim"),
                Text(GUEST, style="dim"),
            ]
        )
        feed = Text("\n").join(Text(line, style=style) for style, line in self.feed)
        return Group(
            Text(f"🎙️ {self.context.task}", style="bold"),
            Panel(
                self._grid(),
                title="clips",
                title_align="left",
                border_style="red" if self.has_broken else BORDER,
            ),
            Panel(
                Group(
                    self._wave(),
                    Text('🧔 "100%"   🧔 "100%"', style="dim"),
                ),
                title="the episode",
                title_align="left",
                border_style=BORDER,
            ),
            counters,
            Panel(
                feed,
                title="subtitles",
                title_align="left",
                border_style="red" if self.has_broken else BORDER,
                height=_FEED_LENGTH + 2,
            ),
            Text("any key: clip faster · esc: stop clipping", style="dim"),
        )


def run(context: AppContext) -> None:
    """Launch the clip farm.

    Args:
        context: The app's context.
    """
    play(
        context,
        ClipfarmScreen(context),
        MELTDOWN,
        success="🎬 your clip got 2M views. the full episode got 31.",
        failure="link in bio (bio deleted)",
    )
