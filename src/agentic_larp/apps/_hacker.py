"""Hacker typer: every key types a chunk of very real code (this package's own source)."""

import random
from pathlib import Path

from rich.align import Align
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.text import Text

from agentic_larp.apps._base import AppContext, run_loop

GREEN = "#39ff14"
_BANNER_SECONDS = 2.2
_DEMO_BANNER_AT = 3.0
_CHUNK = (3, 8)


def load_source(rng: random.Random) -> str:
    """Concatenate this package's Python files in a shuffled order.

    Args:
        rng: Random source for the order.

    Returns:
        A long string of genuine, if irrelevant, code.
    """
    root = Path(__file__).resolve().parent.parent
    files = sorted(root.rglob("*.py"))
    rng.shuffle(files)
    return "\n\n".join(file.read_text(encoding="utf-8") for file in files)


class HackerScreen:
    """Green text on black. Tab flashes ACCESS GRANTED, backtick ACCESS DENIED."""

    def __init__(self, context: AppContext, rng: random.Random | None = None) -> None:
        self.context = context
        self.rng = rng or random.Random()
        self.source = load_source(self.rng)
        self.position = 0
        self.keystrokes = 0
        self.clock = 0.0
        self.banner: str | None = None
        self.banner_at = 0.0
        self.has_demo_banner = False

    def on_key(self, key: str) -> bool:
        """Type more code, or flash a banner.

        Args:
            key: A key name.

        Returns:
            ``False`` on escape.
        """
        if key == "esc":
            return False
        if key == "tab":
            self.show_banner("granted")
        elif key in {"`", "~"}:
            self.show_banner("denied")
        else:
            self.keystrokes += 1
            self.position += self.rng.randint(*_CHUNK)
        return True

    def show_banner(self, kind: str) -> None:
        """Flash ACCESS GRANTED (``"granted"``) or ACCESS DENIED (``"denied"``).

        Args:
            kind: Which banner.
        """
        self.banner, self.banner_at = kind, self.clock

    def tick(self, dt: float) -> bool:
        """Expire banners; in demo mode, type by itself.

        Args:
            dt: Real seconds since the last frame.

        Returns:
            Always ``True``; only the user ends this.
        """
        self.clock += dt
        if self.context.auto is not None:
            self.position += self.rng.randint(0, 9)
            if self.clock > _DEMO_BANNER_AT and not self.has_demo_banner:
                self.has_demo_banner = True
                self.show_banner("granted")
        if self.banner is not None and self.clock - self.banner_at > _BANNER_SECONDS:
            self.banner = None
        return True

    def render(self) -> RenderableType:
        """Draw the code typed so far, or the banner.

        Returns:
            The frame.
        """
        height = self.context.console.size.height
        repeats = self.position // max(1, len(self.source)) + 1
        typed = (self.source * repeats)[: self.position]
        lines = typed.split("\n")[-(height - 2) :]
        cursor = "█" if int(self.clock * 2) % 2 == 0 else " "
        footer = Text(
            f" {self.keystrokes} keystrokes · {self.position:,} chars hacked · "
            "tab: access granted · `: access denied · esc: log off",
            style="dim green",
            no_wrap=True,
            overflow="ellipsis",
        )
        if self.banner is not None:
            is_granted = self.banner == "granted"
            color = GREEN if is_granted else "red"
            label = "ACCESS GRANTED" if is_granted else "ACCESS DENIED"
            is_flash = int(self.clock * 5) % 2 == 0
            style = f"bold black on {color}" if is_flash else f"bold {color}"
            banner = Panel(
                Align.center(Text(label, style=style)),
                border_style=color,
                width=40,
                padding=(1, 2),
            )
            return Group(
                Align.center(banner, vertical="middle", height=height - 1), footer
            )
        body = Text(
            "\n".join(lines) + cursor, style=GREEN, no_wrap=True, overflow="crop"
        )
        padding = Text("\n" * max(0, height - 2 - len(lines)))
        return Group(body, padding, footer)


def run(context: AppContext) -> None:
    """Hack until escape.

    Args:
        context: The app's context.
    """
    run_loop(context, HackerScreen(context))
    context.console.print(f"[{GREEN}]> connection closed. you were never here.[/]")
