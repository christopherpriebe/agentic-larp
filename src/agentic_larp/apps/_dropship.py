"""A dropshipping store dashboard. Every number is a margin."""

import random
from collections import deque

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from agentic_larp.apps._base import App, AppContext
from agentic_larp.apps._flow import BREAK_AT, BREAK_SECONDS, push_feed
from agentic_larp.meltdown import Meltdown, is_doomed, play

BORDER = "#3a4a5a"
PRODUCTS = (
    ("LED Galaxy Projector", 3.12, 49.99),
    ("Posture Corrector (one size)", 1.85, 39.99),
    ("Pet Hair Glove", 0.9, 24.99),
    ("Mini Blender (USB)", 4.4, 59.99),
    ("Moon Lamp 3D", 2.75, 44.99),
)
BUYERS = ("Kyle from Ohio", "Brenda from Texas", "Dave from Leeds", "Priya from Austin")
FAIL_ERRORS = (
    "AliExpress supplier not found",
    "PayPal: account limited",
    "chargeback rate: 340%",
    "Stripe: account frozen pending review",
    "tracking number 000000000 not found",
)
MELTDOWN = Meltdown(errors=FAIL_ERRORS, reveal="jk. your order is still in transit.")
_AD_BURN_PER_MINUTE = 40.0
_ORDER_RATE = 1.2  # orders per second
_FEED_LENGTH = 11
_BOOST_DECAY = 3.0
_MAX_BOOST = 8.0
_FAIL_EVENTS = (
    "supplier banned your account",
    "chargeback: item never arrived",
    "chargeback: item never arrived (again)",
    "chargeback: not as described (it was a different item)",
    "Stripe has frozen your account",
)


class DropshipScreen:
    """Orders roll in, ad spend rolls out, shipping takes 6-8 weeks."""

    def __init__(self, context: AppContext, rng: random.Random | None = None) -> None:
        self.context = context
        self.doomed = is_doomed(context)
        self.rng = rng or context.rng
        self.clock = 0.0
        self.boost = 0.0
        self.revenue = 0.0
        self.ad_spend = 0.0
        self.order_count = 0
        self.feed: deque[tuple[str, str]] = deque(maxlen=_FEED_LENGTH)
        self.broken_at: float | None = None
        self.next_event = 0.0
        self.events = list(_FAIL_EVENTS)

    @property
    def has_broken(self) -> bool:
        """Return whether the store has been shut down."""
        return self.broken_at is not None

    def on_key(self, key: str) -> bool:
        """Run another ad, or close the store.

        Args:
            key: A key name.

        Returns:
            ``False`` on escape.
        """
        if key == "esc":
            return False
        self.boost = min(_MAX_BOOST, self.boost + 1.0)
        return True

    def tick(self, dt: float) -> bool:
        """Take orders, burn ad spend, and (when failing) fall apart.

        Args:
            dt: Real seconds since the last frame.

        Returns:
            ``False`` once a failing store has finished falling apart.
        """
        self.clock += dt
        self.boost = max(0.0, self.boost - dt * _BOOST_DECAY)
        if self.doomed and self.broken_at is None and self.clock >= BREAK_AT:
            self.broken_at = self.next_event = self.clock
        if self.broken_at is not None:
            if self.clock >= self.next_event and self.events:
                self.next_event = self.clock + BREAK_SECONDS / len(_FAIL_EVENTS)
                push_feed(self.feed, "bold red", f"✗ {self.events.pop(0)}")
            return self.clock - self.broken_at < BREAK_SECONDS
        self.ad_spend += dt * _AD_BURN_PER_MINUTE / 60 * (1 + self.boost)
        if self.rng.random() < dt * _ORDER_RATE * (1 + self.boost):
            name, _, price = self.rng.choice(PRODUCTS)
            quantity = self.rng.choice((1, 1, 1, 2, 3))
            self.revenue += price * quantity
            self.order_count += 1
            buyer = self.rng.choice(BUYERS)
            push_feed(self.feed, "green", f"🛒 {buyer} bought {name} ×{quantity}")
        return True

    def render(self) -> RenderableType:
        """Draw the product table, metrics, and orders feed.

        Returns:
            The frame.
        """
        table = Table(box=None, expand=True, padding=(0, 1))
        for column in ("product", "supplier", "price", "margin", "shipping"):
            table.add_column(column, no_wrap=True)
        for name, cost, price in PRODUCTS:
            margin = (price - cost) / price * 100
            table.add_row(
                name, f"${cost:.2f}", f"${price:.2f}", f"{margin:.0f}%", "6-8 weeks"
            )
        roas = Text("improving", style="italic")
        metrics = Table.grid(padding=(0, 2))
        metrics.add_column(style="dim")
        metrics.add_column(style="bold")
        metrics.add_row("revenue", Text(f"${self.revenue:,.2f}", style="bold green"))
        metrics.add_row("orders", f"{self.order_count:,}")
        metrics.add_row("ad spend", Text(f"-${self.ad_spend:,.2f}", style="bold red"))
        metrics.add_row(
            "Meta ads",
            Text.assemble(f"-${_AD_BURN_PER_MINUTE:.0f}/min, ROAS 0.8 '", roas, "'"),
        )
        feed = Text("\n").join(Text(line, style=style) for style, line in self.feed)
        hint = Text("any key: run another ad · esc: close the store", style="dim")
        return Group(
            Text(f"🛍  {self.context.task}  ·  live orders", style="bold"),
            Panel(table, title="products", title_align="left", border_style=BORDER),
            Panel(metrics, title="today", title_align="left", border_style=BORDER),
            Panel(
                feed,
                title="orders",
                title_align="left",
                border_style="red" if self.has_broken else BORDER,
                height=_FEED_LENGTH + 2,
            ),
            hint,
        )


def run(context: AppContext) -> None:
    """Open the store.

    Args:
        context: The app's context.
    """
    play(
        context,
        DropshipScreen(context),
        MELTDOWN,
        success="📦 orders shipped. customers will receive them in 6-8 weeks. or never.",
        failure="your store is now a GoFundMe.",
    )


APP = App(
    "dropship",
    "a dropshipping store: every markup is 1,500%, shipping is 6-8 weeks",
    run,
)
