"""A token launch. The chart is a candlestick-ish bar chart and the LP is locked."""

import math
import random
from collections import deque

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.text import Text

from agentic_larp.apps._base import AppContext
from agentic_larp.apps._chart import draw_chart, make_ticker
from agentic_larp.apps._flow import BREAK_AT, BREAK_SECONDS, push_feed
from agentic_larp.meltdown import Meltdown, is_doomed, play

BORDER = "#3a4a5a"
FAIL_ERRORS = (
    "dev wallet sold 98% of supply",
    "liquidity: 0",
    "telegram admin left the chat",
    "slippage: 100%",
    "contract: ownership was never renounced",
)
MELTDOWN = Meltdown(
    errors=FAIL_ERRORS, reveal="jk. the rug was just a very flat carpet."
)
HYPE = (
    "📣 telegram: WEN MOON?? soon. very soon.",
    "📣 telegram: admin says 'buy the dip' (there was no dip)",
    "📣 telegram: new member count 40,112 (39,000 bots)",
    "📣 telegram: dev is based. dev is doxxed (a stock photo)",
)
_SHARES = 100_000
_CRASH_FACTOR = 0.7
_MIN_PRICE = 1e-12
_MAX_PRICE = 1_000_000.0
_DRIFT = 0.4  # average growth per second
_PUMP_DRIFT = 0.1  # extra growth per second per point of pump
_VOLATILITY = 0.3  # per square-root second
_MIN_STEP = 0.5  # biggest single-step drop, as a price multiple
_CHART_CHROME = 14
_MIN_CHART_HEIGHT = 5
_FEED_LENGTH = 6
_WHALE_RATE = 0.9
_PUMP_DECAY = 4.0
_MAX_PUMP = 30.0
_HOLDER_START = 120


class MemecoinScreen:
    """Holders climb, whales buy, and the liquidity is locked (trust me)."""

    def __init__(self, context: AppContext, rng: random.Random | None = None) -> None:
        self.context = context
        self.doomed = is_doomed(context)
        self.rng = rng or context.rng
        self.symbol = make_ticker(context.task)
        self.prices: deque[float] = deque([10.0], maxlen=400)
        self.holders = _HOLDER_START
        self.clock = 0.0
        self.pump = 0.0
        self.feed: deque[tuple[str, str]] = deque(maxlen=_FEED_LENGTH)
        self.broken_at: float | None = None

    @property
    def has_broken(self) -> bool:
        """Return whether the dev has pulled the liquidity."""
        return self.broken_at is not None

    def on_key(self, key: str) -> bool:
        """Shill harder, or leave.

        Args:
            key: A key name.

        Returns:
            ``False`` on escape.
        """
        if key == "esc":
            return False
        self.pump = min(_MAX_PUMP, self.pump + 2)
        self.holders += self.rng.randint(5, 40)
        return True

    def tick(self, dt: float) -> bool:
        """Move the price, mostly up, until the dev sells.

        Args:
            dt: Real seconds since the last frame.

        Returns:
            ``False`` once a failing launch has finished collapsing.
        """
        self.clock += dt
        if self.doomed and self.broken_at is None and self.clock >= BREAK_AT:
            self.broken_at = self.clock
            self.feed.append(("bold red", "🐋 dev wallet sold 98% of supply"))
            self.feed.append(("bold red", "💧 liquidity removed"))
        if self.broken_at is not None:
            self.prices.append(max(_MIN_PRICE, self.prices[-1] * _CRASH_FACTOR))
            self.holders = max(0, int(self.holders * (1 - dt)))
            return self.clock - self.broken_at < BREAK_SECONDS
        self.pump = max(0.0, self.pump - dt * _PUMP_DECAY)
        drift = (_DRIFT + self.pump * _PUMP_DRIFT) * dt
        step = max(_MIN_STEP, 1 + self.rng.gauss(drift, _VOLATILITY * math.sqrt(dt)))
        self.prices.append(min(_MAX_PRICE, self.prices[-1] * step))
        self.holders += int(self.rng.random() * dt * 60) + 1
        if self.rng.random() < dt * _WHALE_RATE:
            wallet = f"0x{self.rng.randrange(256):02x}…{self.rng.randrange(256):02x}"
            amount = self.rng.uniform(0.5, 9.9)
            push_feed(self.feed, "cyan", f"🐋 {wallet} bought {amount:.1f}M")
        elif self.rng.random() < dt * _WHALE_RATE:
            push_feed(self.feed, "yellow", self.rng.choice(HYPE))
        return True

    def render(self) -> RenderableType:
        """Draw the chart, stats, and whale feed.

        Returns:
            The frame.
        """
        width, height = self.context.console.size
        price = self.prices[-1]
        change = (price / self.prices[0] - 1) * 100
        is_down = self.has_broken
        head = Text.assemble(
            (f"{self.symbol} ", "bold"),
            (f"{change:+,.0f}% ", "bold red" if is_down else "bold green"),
            (f"  market cap ${price * _SHARES:,.0f}", "dim"),
            (f"  holders {self.holders:,}", "bold"),
            ("  LP locked 🔒 (trust me)", "dim"),
        )
        chart_height = max(_MIN_CHART_HEIGHT, height - _CHART_CHROME)
        chart = Panel(
            draw_chart(list(self.prices), width - 4, chart_height),
            title=Text(f"📈 {self.context.task}"),
            title_align="left",
            border_style="red" if is_down else BORDER,
            height=chart_height + 2,
        )
        feed = Text("\n").join(Text(line, style=style) for style, line in self.feed)
        parts: list[RenderableType] = [head, chart, feed]
        if is_down:
            parts.append(Text(" RUG PULLED ", style="bold white on red"))
        return Group(*parts)


def run(context: AppContext) -> None:
    """Launch the token.

    Args:
        context: The app's context.
    """
    screen = MemecoinScreen(context)
    play(
        context,
        screen,
        MELTDOWN,
        success=f"🚀 {screen.symbol} did a 100x. you are early. you are always early.",
        failure="it was a rug. it is always a rug.",
    )
