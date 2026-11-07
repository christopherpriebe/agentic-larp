"""Your startup's ticker. It only goes up. Every keypress is a funding round."""

import random
import re
from collections import deque

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from agentic_larp.apps._base import AppContext, run_loop

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
_MIN_WORD_LENGTH = 3
_TICKER_LETTERS = 4
_MIN_CHART_HEIGHT = 5
_CHART_CHROME = 10
_TICKER_SPEED = 12  # characters per second


def make_ticker(task: str) -> str:
    """Make a ticker symbol from a task's initials.

    Args:
        task: Something like ``"build a billion dollar startup"``.

    Returns:
        ``"$BDS"``, or ``"$LARP"`` when there is nothing to work with.
    """
    words = [
        word
        for word in re.findall(r"[A-Za-z]+", task)
        if len(word) >= _MIN_WORD_LENGTH and word.lower() not in {"build", "the", "and"}
    ]
    letters = "".join(word[0] for word in words).upper()[:_TICKER_LETTERS]
    return f"${letters or 'LARP'}"


def draw_chart(prices: list[float], width: int, height: int) -> Text:
    """Draw the most recent prices as a filled bar chart.

    Args:
        prices: Price history, oldest first.
        width: Columns available; one price per column.
        height: Rows available.

    Returns:
        ``height`` lines, green where the price rose and red where it fell.
    """
    data = prices[-width:]
    low, high = min(data), max(data)
    span = (high - low) or 1
    levels = [(value - low) / span * (height - 1) for value in data]
    rows = []
    for row in range(height - 1, -1, -1):
        line = Text()
        for index, level in enumerate(levels):
            color = "green" if index == 0 or data[index] >= data[index - 1] else "red"
            if level >= row + 0.5:
                line.append("█", style=color)
            elif level >= row:
                line.append("▄", style=color)
            else:
                line.append(" ")
        rows.append(line)
    return Text("\n").join(rows)


class StonksScreen:
    """A price chart, a market cap, and a news crawl."""

    def __init__(self, context: AppContext, rng: random.Random | None = None) -> None:
        self.context = context
        self.rng = rng or random.Random()
        self.symbol = make_ticker(context.task)
        self.prices: deque[float] = deque([10.0], maxlen=400)
        self.clock = 0.0
        self.pump = 0.0
        self.messages = 0
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
            Always ``True``; the user leaves with escape.
        """
        self.clock += dt
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
        head = Table.grid(expand=True)
        head.add_column()
        head.add_column(justify="right")
        head.add_row(
            Text.assemble(
                (f"{self.symbol} ", "bold"),
                (f"${price:,.2f} ", "bold green"),
                (f"▲ {change:,.1f}%", "green"),
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
        offset = int(self.clock * _TICKER_SPEED) % len(self.tape)
        crawl = (self.tape[offset:] + self.tape)[: width - 2]
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
    run_loop(context, screen)
    context.console.print(
        f"[bold green]{screen.symbol}[/] closed at an all-time high. "
        "[dim]you still have $0 in revenue.[/]",
    )
