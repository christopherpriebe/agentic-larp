"""Your startup's ticker. It only goes up. Every keypress is a funding round."""

import random
from collections import deque
from dataclasses import replace

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from agentic_larp.apps._base import AppContext, run_loop
from agentic_larp.apps._chart import draw_chart, make_ticker
from agentic_larp.meltdown import Meltdown, is_doomed, run_meltdown

HEADLINES = (
    "Analysts call {t} 'the future, probably'",
    "{t} up {p}% after founder says 'ship it'",
    "VCs camp outside {t} HQ (a bedroom)",
    "{t} announces AI, stock triples",
    "Report: {t} has never made a dollar, valuation unaffected",
    "{t} hires 20 interns, all of them agents",
    "Short sellers apologize to {t}",
    "{t} added to S&P 500 'for the vibes'",
    "{t} pivots to {t}, investors thrilled",
)
BORDER = "#3a4a5a"
_SHARES = 37_000_000
_MAX_PUMP = 30.0
_MIN_CHART_HEIGHT = 5
_CHART_CHROME = 10
_TICKER_SPEED = 12  # characters per second
_CRASH_AT = 6.0  # seconds before the chart crashes, when failing
_CRASH_SECONDS = 3.0
_CRASH_FACTOR = 0.8  # price multiplier per frame during the crash
_MIN_PRICE = 0.01
CRASH_HEADLINES = (
    "MARGIN CALL",
    "your broker has entered the chat",
    "SEC filing detected",
    "liquidity: none",
)
FAIL_ERRORS = (
    "SEC filing detected",
    "liquidity: none",
    "margin call: 4 missed calls from your broker",
    "order book: empty (it was always empty)",
    "valuation: NaN",
)
MELTDOWN = Meltdown(errors=FAIL_ERRORS, reveal="jk. the SEC says hi.")


class StonksScreen:
    """A price chart, a market cap, and a news crawl."""

    def __init__(self, context: AppContext, rng: random.Random | None = None) -> None:
        self.context = context
        self.doomed = is_doomed(context)
        self.rng = rng or context.rng
        self.symbol = make_ticker(context.task)
        self.prices: deque[float] = deque([10.0], maxlen=400)
        self.clock = 0.0
        self.pump = 0.0
        self.messages = 0
        self.crashed_at: float | None = None
        headlines = [
            line.format(t=self.symbol, p=self.rng.randint(40, 900))
            for line in HEADLINES
        ]
        self.rng.shuffle(headlines)
        self.tape = "   ◆   ".join(headlines) + "   ◆   "

    def on_key(self, key: str) -> bool:
        """Raise a round, or cash out.

        Args:
            key: A key name.

        Returns:
            ``False`` on escape.
        """
        if key == "esc":
            return False
        self.pump = min(_MAX_PUMP, self.pump + 2)
        self.messages += self.rng.randint(1, 4)
        return True

    def tick(self, dt: float) -> bool:
        """Move the price, mostly up.

        Args:
            dt: Real seconds since the last frame.

        Returns:
            ``True`` normally (the user leaves with escape); ``False`` once a
            failing chart has finished crashing.
        """
        self.clock += dt
        if self.doomed and self.crashed_at is None and self.clock >= _CRASH_AT:
            self.crashed_at = self.clock
        if self.crashed_at is not None:
            self.prices.append(max(_MIN_PRICE, self.prices[-1] * _CRASH_FACTOR))
            return self.clock - self.crashed_at < _CRASH_SECONDS
        drift = 0.012 + self.pump * 0.01
        self.pump = max(0.0, self.pump - dt * 4)
        self.prices.append(
            max(1.0, self.prices[-1] * (1 + self.rng.gauss(drift, 0.025)))
        )
        if self.rng.random() < dt * 0.8:
            self.messages += 1
        return True

    def render(self) -> RenderableType:
        """Draw the ticker, chart, stats, and news crawl.

        Returns:
            The frame.
        """
        width, height = self.context.console.size
        price = self.prices[-1]
        change = (price / self.prices[0] - 1) * 100
        is_crashed = self.crashed_at is not None
        head = Table.grid(expand=True)
        head.add_column()
        head.add_column(justify="right")
        head.add_row(
            Text.assemble(
                (f"{self.symbol} ", "bold"),
                (f"${price:,.2f} ", "bold red" if is_crashed else "bold green"),
                (
                    f"▼ {change:,.1f}%" if is_crashed else f"▲ {change:,.1f}%",
                    "red" if is_crashed else "green",
                ),
            ),
            Text.assemble(
                ("market cap ", "dim"), (f"${price * _SHARES:,.0f}", "bold yellow")
            ),
        )
        chart_height = max(_MIN_CHART_HEIGHT, height - _CHART_CHROME)
        graph = Panel(
            draw_chart(list(self.prices), width - 4, chart_height),
            title=Text(f"📈 {self.context.task}"),
            title_align="left",
            border_style=BORDER,
            height=chart_height + 2,
        )
        stats = Text.assemble(
            ("VCs in your DMs: ", "dim"),
            (f"{self.messages:,}", "bold"),
            ("   P/E ratio: ", "dim"),
            ("∞", "bold"),
            ("   revenue: ", "dim"),
            ("$0", "bold red"),
            ("   sentiment: ", "dim"),
            "🚀🚀🚀",
        )
        tape = self.tape
        if is_crashed:
            tape = "   ◆   ".join(CRASH_HEADLINES) + "   ◆   "
            stats = Text(
                "MARGIN CALL · your broker has entered the chat", style="bold red"
            )
        offset = int(self.clock * _TICKER_SPEED) % len(tape)
        crawl = (tape[offset:] + tape)[: width - 2]
        hint = Text("mash keys to raise a round · esc to cash out", style="dim")
        return Group(
            head, graph, stats, Text(crawl, style="bold yellow", no_wrap=True), hint
        )


def run(context: AppContext) -> None:
    """Watch the number go up.

    Args:
        context: The app's context.
    """
    screen = StonksScreen(context)
    is_failing = screen.doomed
    run_loop(replace(context, auto=None) if is_failing else context, screen)
    if screen.crashed_at is not None:
        run_meltdown(context, screen.render(), MELTDOWN)
        context.console.print("your portfolio is a tax write-off now. jk. (mostly)")
        return
    context.console.print(
        f"[bold green]{screen.symbol}[/] closed at an all-time high. "
        "[dim]you still have $0 in revenue.[/]",
    )
