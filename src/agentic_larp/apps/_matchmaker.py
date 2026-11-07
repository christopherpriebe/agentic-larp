"""A calm system assigns you a match, an expiry, and a thousand simulations."""

import random
from collections import deque

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from agentic_larp.apps._base import AppContext
from agentic_larp.apps._flow import BREAK_AT, BREAK_SECONDS, push_feed
from agentic_larp.meltdown import Meltdown, is_doomed, play

BORDER = "#c06a9a"
PINK = "#ff79c6"
MATCH_NAMES = (
    ("Wren Calloway", "W.C."),
    ("Odessa Lund", "O.L."),
    ("Tamsin Vey", "T.V."),
    ("Rowan Ixley", "R.I."),
)
SILHOUETTE = (
    "   .-''-.   ",
    "  /  __  \\  ",
    " |  (  )  | ",
    "  \\  \\/  /  ",
    "   '-..-'   ",
    "  /|    |\\  ",
    " / |____| \\ ",
)
NOTICES = (
    "the system knows what's best 💗",
    "please enjoy your allotted dinner",
    "your feelings have been logged",
    "your pulse is within acceptable limits",
    "thank you for trusting the algorithm",
    "a table for two has been optimized",
    "laughter detected. well done.",
)
PAIRING_EVENTS = (
    "pairing #48,113 settled. they seem content",
    "pairing #48,114 shared an umbrella (approved)",
    "pairing #48,115 expired peacefully",
    "pairing #48,116 held hands (logged)",
    "pairing #48,117 disagreed about toppings (resolved)",
    "pairing #48,118 was told it was destiny",
)
FAIL_ERRORS = (
    "ERR: match reassigned (optimization)",
    "FATAL: feelings.log exceeded quota",
    "WARN: simulation 1,001 refused to run",
    "ERR: countdown reached 00:00:00",
    "ERR: destiny.cfg not found, using defaults",
)
MELTDOWN = Meltdown(
    errors=FAIL_ERRORS, reveal="jk. she was in your timezone all along."
)
_FAIL_LINES = (
    "the system has reassigned you mid-date",
    "your match has been reassigned to a better fit",
    "ERR: match reassigned (optimization)",
    "please do not resist the algorithm 💗",
    "WARN: simulation 1,001 refused to run",
)
_TOTAL_SIMULATIONS = 1000
_SIMULATIONS_PER_SECOND = 55.0
_NUDGE_SIMULATIONS = 15.0
_START_COMPATIBILITY = 41.0
_MAX_COMPATIBILITY = 97.3
_NUDGE_COMPATIBILITY = 0.4
_COMPATIBILITY_PER_SIMULATION = 0.058
_START_SECONDS = 11 * 3600 + 42 * 60
_COUNTDOWN_RATE = 30.0  # simulated seconds that pass per real second
_SECONDS_PER_HOUR = 3600
_SECONDS_PER_MINUTE = 60
_METER_WIDTH = 30
_FEED_LENGTH = 7
_NOTICE_EVERY = 1.6
_EVENT_RATE = 0.8


class MatchmakerScreen:
    """The match card, the countdown, and the climbing compatibility meter."""

    def __init__(self, context: AppContext, rng: random.Random | None = None) -> None:
        self.context = context
        self.doomed = is_doomed(context)
        self.rng = rng or context.rng
        self.name, self.initials = self.rng.choice(MATCH_NAMES)
        self.clock = 0.0
        self.simulations = 0.0
        self.compatibility = _START_COMPATIBILITY
        self.seconds_left = float(_START_SECONDS)
        self.feed: deque[tuple[str, str]] = deque(maxlen=_FEED_LENGTH)
        self.broken_at: float | None = None
        self.next_notice = 0.0
        self.next_line = 0.0
        self.fail_lines = list(_FAIL_LINES)

    @property
    def has_broken(self) -> bool:
        """Return whether the system has reassigned you."""
        return self.broken_at is not None

    def on_key(self, key: str) -> bool:
        """Hold hands, or leave.

        Args:
            key: A key name.

        Returns:
            ``False`` on escape.
        """
        if key == "esc":
            return False
        self.simulations = min(
            _TOTAL_SIMULATIONS, self.simulations + _NUDGE_SIMULATIONS
        )
        self.compatibility = min(
            _MAX_COMPATIBILITY, self.compatibility + _NUDGE_COMPATIBILITY
        )
        push_feed(self.feed, PINK, "💞 hands held. compatibility noted")
        return True

    def tick(self, dt: float) -> bool:
        """Run simulations; when failing, reassign the user mid-date.

        Args:
            dt: Real seconds since the last frame.

        Returns:
            ``False`` once a reassigned user has finished being reassigned.
        """
        self.clock += dt
        if self.doomed and self.broken_at is None and self.clock >= BREAK_AT:
            self.broken_at = self.next_line = self.clock
        if self.broken_at is not None:
            self.seconds_left = max(0.0, self.seconds_left - dt * _START_SECONDS)
            if self.clock >= self.next_line and self.fail_lines:
                self.next_line = self.clock + BREAK_SECONDS / len(_FAIL_LINES)
                push_feed(self.feed, "bold red", self.fail_lines.pop(0))
            return self.clock - self.broken_at < BREAK_SECONDS
        self.seconds_left = max(0.0, self.seconds_left - dt * _COUNTDOWN_RATE)
        before = self.simulations
        self.simulations = min(
            _TOTAL_SIMULATIONS, self.simulations + dt * _SIMULATIONS_PER_SECOND
        )
        self.compatibility = min(
            _MAX_COMPATIBILITY,
            self.compatibility
            + (self.simulations - before) * _COMPATIBILITY_PER_SIMULATION,
        )
        if self.clock >= self.next_notice:
            self.next_notice = self.clock + _NOTICE_EVERY
            push_feed(self.feed, PINK, self.rng.choice(NOTICES))
        elif self.rng.random() < dt * _EVENT_RATE:
            push_feed(self.feed, "dim", self.rng.choice(PAIRING_EVENTS))
        return True

    def _countdown(self) -> Text:
        if self.has_broken:
            return Text("relationship expires in 00:00:00", style="bold red")
        hours, rest = divmod(int(self.seconds_left), _SECONDS_PER_HOUR)
        minutes = rest // _SECONDS_PER_MINUTE
        return Text(f"relationship expires in {hours}h {minutes:02d}m", style="bold")

    def _meter(self) -> Text:
        filled = int(self.compatibility / 100 * _METER_WIDTH)
        return Text.assemble(
            ("█" * filled, PINK),
            ("░" * (_METER_WIDTH - filled), "dim"),
            (f" {self.compatibility:.1f}%", "bold"),
        )

    def render(self) -> RenderableType:
        """Draw the match card, countdown, meter, and notices.

        Returns:
            The frame.
        """
        card = Table.grid(padding=(0, 3))
        card.add_column(style=PINK)
        card.add_column()
        shown = "reassigning..." if self.has_broken else self.name
        card.add_row(
            Text("\n".join(SILHOUETTE)),
            Group(
                Text(shown, style="bold"),
                Text(f"[{self.initials}]", style="dim"),
                Text(""),
                self._countdown(),
            ),
        )
        simulations = Text(
            f"simulation {int(self.simulations):,} / {_TOTAL_SIMULATIONS:,}",
            style="dim",
        )
        return Group(
            Text.assemble(("💘 ", ""), (self.context.task, "bold")),
            Panel(
                card,
                title="your assigned match",
                title_align="left",
                border_style="red" if self.has_broken else BORDER,
            ),
            Panel(
                Group(simulations, self._meter()),
                title="compatibility",
                title_align="left",
                border_style=BORDER,
            ),
            Panel(
                Text("\n").join(Text(line, style=style) for style, line in self.feed),
                title="system notices",
                title_align="left",
                border_style="red" if self.has_broken else BORDER,
                height=_FEED_LENGTH + 2,
            ),
            Text("any key: hold hands · esc: leave the date", style="dim"),
        )


def run(context: AppContext) -> None:
    """Launch the matchmaker.

    Args:
        context: The app's context.
    """
    play(
        context,
        MatchmakerScreen(context),
        MELTDOWN,
        success="💞 1,000 of 1,000 simulations ordered the same dessert. match: 97.3%. "
        "the system is… happy for you.",
        failure="you have been reassigned. please do not resist the algorithm. 💗",
    )
