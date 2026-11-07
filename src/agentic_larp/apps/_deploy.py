"""A global production rollout. Every number is made up and every number is green."""

import random
from collections import deque

from rich.align import Align
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.table import Table
from rich.text import Text

from agentic_larp.apps._base import AppContext, run_loop

REGIONS = (
    "us-east-1",
    "us-west-2",
    "eu-west-1",
    "eu-central-1",
    "ap-south-1",
    "ap-northeast-1",
    "sa-east-1",
    "af-south-1",
    "mars-north-1",
)
EVENTS = (
    "canary at 1%: vibes nominal",
    "canary at 5%: still fine",
    "canary at 25%: nobody noticed",
    "pagerduty: silent",
    "CEO liked the deploy tweet",
    "skipped staging (it's friday)",
    "cache warmed by sheer confidence",
    "rollback plan located: README.md, line 1",
    "SLO budget: unlimited (we removed the SLO)",
    "load balancer: balanced",
    "error rate rounded down to 0.00%",
    "on-call engineer still asleep (good sign)",
)
BORDER = "#3a4a5a"
_BLOCKS = " ▁▂▃▄▅▆▇█"
_COMPLETE = 100.0
_REGION_STAGGER = 0.5
_MAX_BOOST = 10.0
_SPARK_POINTS = 30


def sparkline(values: list[float]) -> str:
    """Draw values as a row of block characters scaled to their maximum.

    Args:
        values: Non-negative numbers.

    Returns:
        One character per value.
    """
    peak = max(values, default=0) or 1
    top = len(_BLOCKS) - 1
    return "".join(_BLOCKS[min(top, int(value / peak * top))] for value in values)


class DeployScreen:
    """Regions roll out one by one; mashing keys speeds it up."""

    def __init__(self, context: AppContext, rng: random.Random | None = None) -> None:
        self.context = context
        self.rng = rng or random.Random()
        self.progress = dict.fromkeys(REGIONS, 0.0)
        self.speed = {region: self.rng.uniform(4, 14) for region in REGIONS}
        self.traffic = deque(
            [self.rng.uniform(800, 1200) for _ in range(60)], maxlen=60
        )
        self.events: deque[tuple[str, str]] = deque(maxlen=12)
        self.upcoming = list(EVENTS)
        self.rng.shuffle(self.upcoming)
        self.clock = 0.0
        self.boost = 0.0
        self.next_event = 0.5
        self.done_at: float | None = None

    def on_key(self, key: str) -> bool:
        """Speed things up, or leave.

        Args:
            key: A key name.

        Returns:
            ``False`` on escape, or on any key once shipped.
        """
        if key == "esc" or self.done_at is not None:
            return False
        self.boost = min(_MAX_BOOST, self.boost + 1.5)
        return True

    def tick(self, dt: float) -> bool:
        """Advance every region and the metrics.

        Args:
            dt: Real seconds since the last frame.

        Returns:
            Always ``True``; the user leaves with a key.
        """
        self.clock += dt
        boost = 1 + self.boost
        self.boost = max(0.0, self.boost - dt * 3)
        for index, region in enumerate(REGIONS):
            if (
                self.clock > index * _REGION_STAGGER
                and self.progress[region] < _COMPLETE
            ):
                step = dt * self.speed[region] * boost * self.rng.uniform(0.3, 1.7)
                self.progress[region] = min(_COMPLETE, self.progress[region] + step)
                if self.progress[region] >= _COMPLETE:
                    self.events.append(("green", f"✓ rolled out to {region}"))
        self.traffic.append(
            max(100, self.traffic[-1] * self.rng.uniform(0.96, 1.06) + 15)
        )
        if self.clock > self.next_event and self.upcoming:
            self.events.append(("dim", self.upcoming.pop()))
            self.next_event = self.clock + self.rng.uniform(0.8, 2.0)
        if self.done_at is None and self.is_shipped:
            self.done_at = self.clock
            self.events.append(("bold green", "🚀 100% of traffic on new version"))
        return True

    @property
    def is_shipped(self) -> bool:
        """Return whether every region is at 100%."""
        return all(value >= _COMPLETE for value in self.progress.values())

    def render(self) -> RenderableType:
        """Draw regions, metrics, and the event log.

        Returns:
            The frame.
        """
        regions = Table(box=None, expand=True, padding=(0, 1))
        regions.add_column("region", style="bold", no_wrap=True)
        regions.add_column("rollout", ratio=1)
        regions.add_column("", justify="right", no_wrap=True)
        regions.add_column("status", no_wrap=True)
        for region in REGIONS:
            value = self.progress[region]
            if value >= _COMPLETE:
                status = Text("✓ live", style="green")
            elif value == 0:
                status = Text("◌ queued", style="dim")
            else:
                status = Text("⟳ rolling", style="yellow")
            bar = ProgressBar(
                total=_COMPLETE,
                completed=value,
                complete_style="green",
                finished_style="bold green",
            )
            regions.add_row(region, bar, f"{value:5.1f}%", status)

        average = sum(self.progress.values()) / len(self.progress)
        metrics = Table.grid(padding=(0, 2))
        metrics.add_column(style="dim")
        metrics.add_column(style="bold green")
        recent = list(self.traffic)[-_SPARK_POINTS:]
        metrics.add_row("requests/s", f"{self.traffic[-1]:,.0f}  {sparkline(recent)}")
        metrics.add_row("error rate", "0.00%")
        metrics.add_row("p99 latency", f"{self.rng.uniform(3.6, 4.4):.1f}ms")
        metrics.add_row("uptime", "100.000%")
        metrics.add_row("vibes", "immaculate")
        metrics.add_row("rollout", f"{average:.1f}%")

        events = Text("\n").join(
            Text(message, style=style) for style, message in self.events
        )
        top = Table.grid(expand=True)
        top.add_column(ratio=3)
        top.add_column(ratio=2)
        top.add_row(
            Panel(regions, title="🌍 regions", title_align="left", border_style=BORDER),
            Panel(metrics, title="📈 metrics", title_align="left", border_style=BORDER),
        )
        title = Text.assemble(
            ("🚀 deploying ", "bold"),
            (self.context.task, "bold cyan"),
            (f"   T+{self.clock:4.1f}s", "dim"),
        )
        parts: list[RenderableType] = [
            title,
            top,
            Panel(
                events,
                title="📜 events",
                title_align="left",
                border_style=BORDER,
                height=14,
            ),
        ]
        if self.done_at is not None:
            is_flash = int(self.clock * 3) % 2 == 0
            banner = Text(
                " SHIPPED TO PROD. NOBODY GOT PAGED. ",
                style="bold black on green" if is_flash else "bold green",
            )
            parts += [
                Align.center(banner),
                Align.center(Text("press any key", style="dim")),
            ]
        else:
            hint = "mash keys to deploy faster · esc to abort (you won't)"
            parts.append(Align.center(Text(hint, style="dim")))
        return Group(*parts)


def run(context: AppContext) -> None:
    """Roll out everywhere at once.

    Args:
        context: The app's context.
    """
    run_loop(context, DeployScreen(context))
    context.console.print(
        "[bold green]🚀 shipped.[/] [dim]if anything breaks, it was the intern.[/]",
    )
