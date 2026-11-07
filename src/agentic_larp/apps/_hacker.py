"""Hack the planet: scan, dump memory, crack a password, outrun the trace."""

import random
from dataclasses import replace

from rich.align import Align
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.text import Text

from agentic_larp.apps._base import AppContext, run_loop
from agentic_larp.meltdown import Meltdown, is_doomed, run_meltdown

GREEN = "#39ff14"
STAGES = ("SCANNING", "DUMPING MEMORY", "CRACKING PASSWORD", "TRACING")
FAIL_ERRORS = (
    "firewall fought back",
    "they hacked you back",
    "your IP is on the news",
    "trace route ends at your kitchen",
    "ISP: we have notified your mother",
)
MELTDOWN = Meltdown(errors=FAIL_ERRORS, reveal="jk. the fbi van was just a delivery.")
_RUN_SECONDS = 21.0  # the whole hack with no keys pressed
_KEY_PROGRESS = 0.012
_BANNER_SECONDS = 3.0
_TRACED_SECONDS = 2.5
_FLASH_SECONDS = 2.2
_TRACE_WINS_AT = 0.6  # share of the TRACING stage after which the trace wins
_SCAN_STAGE, _DUMP_STAGE, _CRACK_STAGE = 0, 1, 2
_SCAN_LINES = 40
_DUMP_ROWS = 60
_DUMP_WIDTH = 16
_CHROME_ROWS = 5
_MAP_WIDTH = 60
_MAP = (
    "        ..::::..            .::.     ..:::::::::::..          ",
    "    ..::::::::::::.       ..::::.   .::::::::::::::::::.      ",
    "   .::::::::::::::.        ..::.    ::::::::::::::::::::.     ",
    "    .:::::::::::.           ..      .::::::::::::::::::.      ",
    "      ..:::::::.        .:::::::.      ::::::::::..:::.       ",
    "         .::::.        .:::::::::.      .::::.     ..::.      ",
    "          .:::.         ::::::::::       ..::.        .       ",
    "          .::::          .:::::::.                    ..::.   ",
    "           .::.            .:::::.                  .:::::.   ",
    "            ..               .::.                    ..::.    ",
)
_CITIES = (
    ("San Francisco", 6, 3),
    ("New York", 16, 2),
    ("Sao Paulo", 18, 7),
    ("London", 29, 1),
    ("Lagos", 31, 5),
    ("Moscow", 39, 1),
    ("Mumbai", 42, 4),
    ("Tokyo", 54, 3),
    ("Sydney", 53, 8),
)
_PASSWORDS = ("hunter2!", "correcthorse", "p@ssw0rd1", "letmein_42", "admin123")
_SERVICES = ("ssh", "http", "https", "smtp", "mysql", "redis", "ftp", "rdp", "vibes")
_PRINTABLE = range(33, 127)
_NOISE = "!#$%&*+=?@^~0123456789abcdef"


def _hex_row(rng: random.Random, address: int) -> str:
    data = [rng.randrange(256) for _ in range(_DUMP_WIDTH)]
    cells = " ".join(f"{byte:02x}" for byte in data)
    text = "".join(chr(byte) if byte in _PRINTABLE else "." for byte in data)
    return f"0x7ffe3a{address & 0xFF:02x}  {cells}  |{text}|"


class HackerScreen:
    """Four stages of hacking that advance by themselves, and faster per keypress."""

    def __init__(self, context: AppContext, rng: random.Random | None = None) -> None:
        self.context = context
        self.doomed = is_doomed(context)
        self.rng = rng or context.rng
        self.progress = 0.0
        self.keystrokes = 0
        self.clock = 0.0
        self.banner: str | None = None
        self.banner_at = 0.0
        self.phase = "hacking"  # then "granted" or "traced"
        self.phase_at = 0.0
        self.password = self.rng.choice(_PASSWORDS)
        self.scan = [
            f"PORT {self.rng.choice((22, 80, 443, 3306, 6379, 8080, 31337))}/tcp "
            f"open {self.rng.choice(_SERVICES)}   "
            f"10.{self.rng.randrange(256)}.{self.rng.randrange(256)}."
            f"{self.rng.randrange(1, 255)}"
            for _ in range(_SCAN_LINES)
        ]
        self.dump = [_hex_row(self.rng, 16 * i) for i in range(_DUMP_ROWS)]
        self.route = self.rng.sample(_CITIES, 6)

    @property
    def is_failing(self) -> bool:
        """Return whether this hack ends in a trace."""
        return self.doomed

    def on_key(self, key: str) -> bool:
        """Speed the hack up, flash a banner, or log off.

        Args:
            key: A key name.

        Returns:
            ``False`` on escape.
        """
        if key == "esc":
            return False
        if key == "tab":
            self.banner = "denied" if self.is_failing else "granted"
            self.banner_at = self.clock
        elif key in {"`", "~"}:
            self.banner, self.banner_at = "denied", self.clock
        else:
            self.keystrokes += 1
            if self.phase == "hacking":
                self.progress += _KEY_PROGRESS
        return True

    def tick(self, dt: float) -> bool:
        """Advance the hack and its banners.

        Args:
            dt: Real seconds since the last frame.

        Returns:
            ``False`` once the final banner has been held long enough.
        """
        self.clock += dt
        if self.banner is not None and self.clock - self.banner_at > _FLASH_SECONDS:
            self.banner = None
        if self.phase == "hacking":
            self.progress += dt / _RUN_SECONDS
            stage, local = self._stage()
            if self.is_failing and stage == len(STAGES) - 1 and local >= _TRACE_WINS_AT:
                self.phase, self.phase_at = "traced", self.clock
            elif not self.is_failing and self.progress >= 1:
                self.phase, self.phase_at = "granted", self.clock
            return True
        hold = _TRACED_SECONDS if self.phase == "traced" else _BANNER_SECONDS
        return self.clock - self.phase_at <= hold

    def _stage(self) -> tuple[int, float]:
        scaled = min(self.progress, 0.999999) * len(STAGES)
        return int(scaled), scaled - int(scaled)

    def render(self) -> RenderableType:
        """Draw the current stage, or a banner.

        Returns:
            The frame.
        """
        height = self.context.console.size.height
        tab_hint = "tab: access denied" if self.is_failing else "tab: access granted"
        footer = Text(
            f" {self.keystrokes} keystrokes · every key hacks faster · "
            f"{tab_hint} · `: access denied · esc: log off",
            style="dim green",
            no_wrap=True,
            overflow="ellipsis",
        )
        if self.phase != "hacking" or self.banner is not None:
            return Group(self._render_banner(height), footer)
        stage, local = self._stage()
        header = Text(
            f"[{stage + 1}/{len(STAGES)}] {STAGES[stage]}  {int(local * 100):3d}%",
            style=f"bold {GREEN}",
        )
        room = max(3, height - _CHROME_ROWS)
        if stage == _SCAN_STAGE:
            body = self._scan(local, room)
        elif stage == _DUMP_STAGE:
            body = self._dump(local, room)
        elif stage == _CRACK_STAGE:
            body = self._crack(local)
        else:
            body = self._trace(local, room)
        padding = Text("\n" * max(0, room - body.plain.count("\n") - 1))
        return Group(header, Text(""), body, padding, footer)

    def _render_banner(self, height: int) -> RenderableType:
        is_granted = self.phase == "granted" or self.banner == "granted"
        is_traced = self.phase == "traced"
        if is_traced:
            label, color, extra = "TRACE COMPLETE", "red", "THEY KNOW WHERE YOU LIVE."
        elif is_granted:
            label, color, extra = "ACCESS GRANTED", GREEN, "you are in. act natural."
        else:
            label, color, extra = "ACCESS DENIED", "red", "nice try."
        is_flash = int(self.clock * 5) % 2 == 0
        style = f"bold black on {color}" if is_flash else f"bold {color}"
        banner = Panel(
            Align.center(Text(f"\n{label}\n", style=style)),
            subtitle=extra,
            border_style=color,
            width=50,
            padding=(2, 4),
        )
        return Align.center(banner, vertical="middle", height=height - 1)

    def _scan(self, local: float, room: int) -> Text:
        count = int(local * len(self.scan)) + 1
        return Text("\n".join(self.scan[:count][-room:]), style=GREEN, no_wrap=True)

    def _dump(self, local: float, room: int) -> Text:
        count = int(local * len(self.dump)) + 1
        return Text("\n".join(self.dump[:count][-room:]), style=GREEN, no_wrap=True)

    def _crack(self, local: float) -> Text:
        locked = int(local * len(self.password))
        noise = "".join(self.rng.choice(_NOISE) for _ in self.password[locked:])
        attempts = int(local * 9_000_000) + self.keystrokes
        text = (
            f"target: root@mainframe\nwordlist: rockyou.txt\n"
            f"attempts: {attempts:,}\n\npassword: {self.password[:locked]}{noise}"
        )
        return Text(text, style=GREEN, no_wrap=True)

    def _trace(self, local: float, room: int) -> Text:
        grid = [list(row.ljust(_MAP_WIDTH)) for row in _MAP]
        hops = len(self.route)
        reached = local * (hops - 1)
        for index in range(hops - 1):
            fraction = min(1.0, max(0.0, reached - index))
            if fraction == 0:
                break
            (_, c1, r1), (_, c2, r2) = self.route[index], self.route[index + 1]
            steps = max(abs(c2 - c1), abs(r2 - r1), 1)
            for step in range(int(steps * fraction) + 1):
                col = c1 + round((c2 - c1) * step / steps)
                row = r1 + round((r2 - r1) * step / steps)
                grid[row][col] = "·"
        for index, (_, col, row) in enumerate(self.route):
            if index <= reached:
                grid[row][col] = "◉" if index == int(reached) else "o"
        current = self.route[min(hops - 1, int(reached))][0]
        hop = f"hop {min(hops, int(reached) + 1)}/{hops}: {current} (proxy)"
        rows = ["".join(row) for row in grid[:room]]
        return Text("\n".join([*rows, "", hop]), style=GREEN, no_wrap=True)


def run(context: AppContext) -> None:
    """Hack, then either get in or get traced.

    Args:
        context: The app's context.
    """
    screen = HackerScreen(context)
    is_failing = screen.doomed
    run_loop(replace(context, auto=None) if is_failing else context, screen)
    if screen.phase == "traced":
        run_meltdown(context, screen.render(), MELTDOWN)
        context.console.print("they traced you to a starbucks. good luck.")
        return
    context.console.print(f"[{GREEN}]> connection closed. you were never here.[/]")
