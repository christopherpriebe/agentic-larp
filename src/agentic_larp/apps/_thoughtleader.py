"""A professional-network post composer that writes cringe broetry live."""

import random
from collections import deque

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from agentic_larp.apps._base import AppContext, Outcome
from agentic_larp.apps._flow import BREAK_AT, BREAK_SECONDS, play, push_feed

BORDER = "#3a4a5a"
POST_LINES = (
    "I fired my best engineer today.",
    "(No one was fired.)",
    "Here's what it taught me about B2B sales 👇",
    "Last week I was humbled.",
    "Then I was humbled again.",
    "A barista asked me what I do.",
    "I said: I scale empathy.",
    "She said: that'll be $6.",
    "Leadership is a latte.",
    "Failure is just a pivot with extra steps.",
    "I'm thrilled to announce nothing.",
    "Agree?",
)
BOT_COMMENTS = (
    "Great insights! 🙌",
    "Love this! 💡",
    "So true! 👏",
    "Thanks for sharing!",
    "CFBR",
)
FAIL_ERRORS = (
    "ERR: authenticity_score = -12",
    "FATAL: recruiter asked 'did you write this?'",
    "PANIC: post was just the agent's system prompt",
    "WARN: flagged as AI-generated",
    "ERR: comment pod unreachable",
)
_FAIL_LINES = (
    "⚠ flagged as AI-generated",
    "authenticity_score = -12",
    "recruiter: did you write this?",
    "recruiter: did you write this?? (3 mutual connections)",
    "Agree?",
)
_FAIL_DEATH_LINE = "Agree? (connection lost)"
_REACTIONS = ("👏", "💡", "🙌")
_ROBOT = "🤖"
_LINE_SECONDS = 0.9
_FEED_LENGTH = 6
_POST_LENGTH = 9
_START_IMPRESSIONS = 120
_IMPRESSIONS_PER_SECOND = 900.0
_MAX_IMPRESSIONS = 2_100_000
_MAX_COUNT = 999_999
_MAX_PUSH = 8.0
_PUSH_DECAY = 3.0
_COMMENT_RATE = 1.2
_START_DENSITY = 60
_MAX_DENSITY = 94
_DENSITY_TARGET = 95


class ThoughtleaderScreen:
    """A post typing itself out while the numbers climb."""

    def __init__(self, context: AppContext, rng: random.Random | None = None) -> None:
        self.context = context
        self.rng = rng or random.Random()
        self.clock = 0.0
        self.push = 0.0
        self.impressions = float(_START_IMPRESSIONS)
        self.lines_typed = 0
        self.next_typed = 0.0
        self.post: deque[str] = deque(maxlen=_POST_LENGTH)
        self.reactions = [0, 0, 0]
        self.comment_counts: dict[str, int] = {}
        self.feed: deque[tuple[str, str]] = deque(maxlen=_FEED_LENGTH)
        self.broken_at: float | None = None
        self.next_line = 0.0
        self.fail_lines = list(_FAIL_LINES)

    @property
    def has_broken(self) -> bool:
        """Return whether the post has been flagged."""
        return self.broken_at is not None

    def on_key(self, key: str) -> bool:
        """Boost the post, or give up.

        Args:
            key: A key name.

        Returns:
            ``False`` on escape.
        """
        if key == "esc":
            return False
        self.push = min(_MAX_PUSH, self.push + 1.0)
        return True

    def _type_line(self) -> None:
        """Add the next sentence of the post."""
        self.post.append(POST_LINES[self.lines_typed % len(POST_LINES)])
        self.lines_typed = min(_MAX_COUNT, self.lines_typed + 1)

    def _react(self, dt: float) -> None:
        """Gain reactions and the occasional bot comment."""
        rate = 1 + self.push
        for index in range(len(self.reactions)):
            gained = int(self.rng.random() < dt * 6 * rate) * self.rng.randint(1, 40)
            self.reactions[index] = min(_MAX_COUNT, self.reactions[index] + gained)
        if self.rng.random() < dt * _COMMENT_RATE * rate:
            comment = self.rng.choice(BOT_COMMENTS)
            count = min(_MAX_COUNT, self.comment_counts.get(comment, 0) + 1)
            self.comment_counts[comment] = count
            push_feed(self.feed, "green", f"{comment} ×{count:,}")

    def tick(self, dt: float) -> bool:
        """Type, count, and when failing, get flagged.

        Args:
            dt: Real seconds since the last frame.

        Returns:
            ``False`` once a failing post has finished falling over.
        """
        self.clock += dt
        self.push = max(0.0, self.push - dt * _PUSH_DECAY)
        if (
            self.context.outcome is Outcome.FAIL
            and self.broken_at is None
            and self.clock >= BREAK_AT
        ):
            self.broken_at = self.next_line = self.clock
        if self.broken_at is not None:
            if self.clock >= self.next_line and self.fail_lines:
                self.next_line = self.clock + BREAK_SECONDS / len(_FAIL_LINES)
                push_feed(self.feed, "bold red", self.fail_lines.pop(0))
            return self.clock - self.broken_at < BREAK_SECONDS
        if self.clock >= self.next_typed:
            self.next_typed = self.clock + _LINE_SECONDS
            self._type_line()
        gained = dt * _IMPRESSIONS_PER_SECOND * (1 + self.push) * (1 + self.clock / 2)
        self.impressions = min(_MAX_IMPRESSIONS, self.impressions + gained)
        self._react(dt)
        return True

    def _density(self) -> int:
        return min(_MAX_DENSITY, _START_DENSITY + self.lines_typed * 3)

    def _reaction_column(self) -> Text:
        if self.has_broken:
            return Text("\n".join(f"{_ROBOT} {_ROBOT}" for _ in _REACTIONS))
        return Text(
            "\n".join(
                f"{emoji} {count:,}"
                for emoji, count in zip(_REACTIONS, self.reactions, strict=True)
            )
        )

    def render(self) -> RenderableType:
        """Draw the post, the reactions, the comments, and the stats.

        Returns:
            The frame.
        """
        post = Text("\n").join(Text(line) for line in self.post)
        body = Table.grid(padding=(0, 3))
        body.add_column(ratio=3)
        body.add_column()
        body.add_row(post, self._reaction_column())
        breaks = self.lines_typed
        stats = (
            f"line breaks: {breaks} · sentences: {breaks}"
            f"   humblebrag density: {self._density()}% (target: {_DENSITY_TARGET}%)"
        )
        feed = Text("\n").join(Text(line, style=style) for style, line in self.feed)
        return Group(
            Text.assemble(("📣 ", "bold"), (self.context.task, "bold")),
            Panel(
                body,
                title="new post",
                title_align="left",
                border_style="red" if self.has_broken else BORDER,
                height=_POST_LENGTH + 2,
            ),
            Text(f"👁 {int(self.impressions):,} impressions", style="bold cyan"),
            Text(stats, style="dim"),
            Panel(
                feed,
                title="comments",
                title_align="left",
                border_style="red" if self.has_broken else BORDER,
                height=_FEED_LENGTH + 2,
            ),
            Text("any key: boost post · esc: delete draft", style="dim"),
        )


def run(context: AppContext) -> None:
    """Launch the thoughtleader.

    Args:
        context: The app's context.
    """
    play(
        context,
        ThoughtleaderScreen(context),
        FAIL_ERRORS,
        "📣 posted. 2.1M impressions. now go thank your barista. then post about it.",
        _FAIL_DEATH_LINE,
    )
