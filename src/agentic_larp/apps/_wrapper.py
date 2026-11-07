"""An AI startup that is one API call, racing its MRR against its API bill."""

import random
from collections import deque

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from agentic_larp.apps._base import App, AppContext
from agentic_larp.apps._flow import BREAK_AT, BREAK_SECONDS, push_feed
from agentic_larp.meltdown import Meltdown, is_doomed, play

BORDER = "#3a4a5a"
PITCH = "we're the Stripe of prompts"
SOURCE = "def product(prompt):\n    return llm(prompt)\n"
SIGNUPS = (
    "chad@stealth.ai (free tier)",
    "priya@seriesA.io (annual plan, refunded)",
    "dave@gmail.com (just looking)",
    "founder@yc-adjacent.co (wants a demo)",
)
FAIL_ERRORS = (
    "429 Too Many Requests (x9000)",
    "upstream provider shipped your feature",
    "burn: infinite",
    "API key revoked",
    "invoice: $48,000 (net 0)",
)
MELTDOWN = Meltdown(errors=FAIL_ERRORS, reveal="jk. the API bill was in euros.")
_MRR_PER_SECOND = 55.0
_BILL_PER_SECOND = 48.0
_START_MRR = 2400.0
_START_BILL = 2100.0
_BILL_SPIKE = 25.0
_MAX_BILL = 9_999_999_999.0
_BAR_WIDTH = 40
_FEED_LENGTH = 8
_SIGNUP_RATE = 1.0
_PUSH_DECAY = 3.0
_MAX_PUSH = 8.0
_FAIL_LINES = (
    "429 Too Many Requests",
    "429 Too Many Requests (and counting)",
    "provider: your API key has been revoked",
    "rate limit exceeded (retrying... retrying... retrying...)",
    "pivoting to hardware",
)


class WrapperScreen:
    """MRR and the API bill, neck and neck."""

    def __init__(self, context: AppContext, rng: random.Random | None = None) -> None:
        self.context = context
        self.doomed = is_doomed(context)
        self.rng = rng or context.rng
        self.clock = 0.0
        self.push = 0.0
        self.mrr = _START_MRR
        self.bill = _START_BILL
        self.feed: deque[tuple[str, str]] = deque(maxlen=_FEED_LENGTH)
        self.broken_at: float | None = None
        self.next_line = 0.0
        self.fail_lines = list(_FAIL_LINES)

    @property
    def has_broken(self) -> bool:
        """Return whether the API bill has overtaken the revenue."""
        return self.broken_at is not None

    def on_key(self, key: str) -> bool:
        """Send a growth hack, or give up.

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
        """Grow MRR and the bill; when failing, the bill wins.

        Args:
            dt: Real seconds since the last frame.

        Returns:
            ``False`` once a failing startup has finished falling over.
        """
        self.clock += dt
        self.push = max(0.0, self.push - dt * _PUSH_DECAY)
        if self.doomed and self.broken_at is None and self.clock >= BREAK_AT:
            self.broken_at = self.next_line = self.clock
        if self.broken_at is not None:
            self.bill = min(_MAX_BILL, self.bill * (1 + dt * _BILL_SPIKE))
            if self.clock >= self.next_line and self.fail_lines:
                self.next_line = self.clock + BREAK_SECONDS / len(_FAIL_LINES)
                push_feed(self.feed, "bold red", self.fail_lines.pop(0))
            return self.clock - self.broken_at < BREAK_SECONDS
        self.mrr += dt * _MRR_PER_SECOND * (1 + self.push)
        self.bill += dt * _BILL_PER_SECOND * (1 + self.push * 0.8)
        if self.rng.random() < dt * _SIGNUP_RATE * (1 + self.push):
            signup = f"🎉 new signup: {self.rng.choice(SIGNUPS)}"
            push_feed(self.feed, "green", signup)
        return True

    def _bar(self, value: float, scale: float, style: str) -> Text:
        filled = min(_BAR_WIDTH, int(value / scale * _BAR_WIDTH))
        return Text("█" * filled, style=style)

    def render(self) -> RenderableType:
        """Draw MRR against the bill, the pitch, the product, and signups.

        Returns:
            The frame.
        """
        scale = max(self.mrr, self.bill) * 1.05
        race = Table.grid(padding=(0, 2))
        race.add_column(style="dim")
        race.add_column(no_wrap=True)
        race.add_column(justify="right", style="bold")
        is_losing = self.bill > self.mrr
        race.add_row("MRR", self._bar(self.mrr, scale, "green"), f"${self.mrr:,.0f}")
        race.add_row(
            "API bill",
            self._bar(self.bill, scale, "red"),
            Text(f"${self.bill:,.0f}", style="bold red" if is_losing else "bold"),
        )
        feed = Text("\n").join(Text(line, style=style) for style, line in self.feed)
        return Group(
            Text.assemble(
                (f"🤖 {self.context.task}", "bold"), (f'  "{PITCH}"', "italic dim")
            ),
            Panel(
                race, title="MRR vs API bill", title_align="left", border_style=BORDER
            ),
            Panel(
                Syntax(SOURCE, "python", background_color="default"),
                title="the product (entire)",
                title_align="left",
                border_style=BORDER,
            ),
            Panel(
                feed,
                title="signups",
                title_align="left",
                border_style="red" if self.has_broken else BORDER,
                height=_FEED_LENGTH + 2,
            ),
            Text("any key: ship a growth hack · esc: pivot", style="dim"),
        )


def run(context: AppContext) -> None:
    """Launch the wrapper.

    Args:
        context: The app's context.
    """
    play(
        context,
        WrapperScreen(context),
        MELTDOWN,
        success="💸 MRR passed the API bill. barely. raise a seed round immediately.",
        failure="the model provider released your app as a free feature.",
    )


APP = App("wrapper", "an AI startup that is one API call, racing its API bill", run)
