"""What every payoff app shares: its context, the screen protocol, and the loop."""

import time
from collections.abc import Callable
from contextlib import nullcontext
from dataclasses import dataclass
from enum import StrEnum
from importlib.metadata import entry_points
from typing import Protocol, TypeAlias

from rich.console import Console, RenderableType
from rich.live import Live

from agentic_larp._keys import Keys, KeySource

ENTRY_POINT_GROUP = "agentic_larp.apps"
_MAX_DT = 0.25


class Outcome(StrEnum):
    """How an app ends: with a flourish, or with a meltdown."""

    SUCCESS = "success"
    FAIL = "fail"


@dataclass(frozen=True, slots=True)
class AppContext:
    """Everything an app gets when it launches.

    Attributes:
        console: Where to draw.
        task: What the agents "built", for flavor text.
        auto: Exit on its own after this many seconds (demo mode), or never.
        fps: Frames per second.
        keys: Key source to read from; ``None`` reads the real keyboard.
        outcome: Whether the app should end well or break and melt down.
    """

    console: Console
    task: str
    auto: float | None = None
    fps: int = 20
    keys: KeySource | None = None
    outcome: Outcome = Outcome.SUCCESS


class Screen(Protocol):
    """A full-screen app driven by :func:`run_loop`."""

    def render(self) -> RenderableType:
        """Build the current frame."""
        ...

    def on_key(self, key: str) -> bool:
        """Handle a keypress; return ``False`` to exit."""
        ...

    def tick(self, dt: float) -> bool:
        """Advance by ``dt`` real seconds; return ``False`` to exit."""
        ...


App: TypeAlias = Callable[[AppContext], None]


def run_loop(context: AppContext, screen: Screen) -> None:
    """Drive a screen full screen until it, the user, or demo mode ends it.

    Args:
        context: The app's context.
        screen: The screen to draw and feed keys to.
    """
    source = context.keys or Keys()
    with (
        source if isinstance(source, Keys) else nullcontext(),
        Live(
            screen.render(),
            console=context.console,
            screen=True,
            auto_refresh=False,
            transient=True,
        ) as live,
    ):
        start = last = time.monotonic()
        while True:
            if not all(screen.on_key(key) for key in source.read()):
                return
            now = time.monotonic()
            if not screen.tick(min(_MAX_DT, now - last)):
                return
            last = now
            if context.auto is not None and now - start > context.auto:
                return
            live.update(screen.render(), refresh=True)
            time.sleep(max(0.0, 1 / context.fps - (time.monotonic() - now)))


DESCRIPTIONS = {
    "call": "someone who loves you calls (the agents built her)",
    "hacker": "hack the planet: scan, dump, crack, trace (mash keys to go faster)",
    "deploy": "a global prod rollout that definitely won't page anyone",
    "stonks": "your startup's stock, which only goes up",
    "dropship": "a dropshipping store: every markup is 1,500%, shipping is 6-8 weeks",
    "memecoin": "a token launch: the liquidity is locked (trust me)",
    "wrapper": "an AI startup that is one API call, racing its API bill",
    "nft": "an NFT mint: a pixel ape, a floor price, and a jpeg",
}


def app_registry() -> dict[str, App]:
    """Return every app by name: the built-ins, then installed plugins.

    Plugins register under the ``agentic_larp.apps`` entry-point group. A
    plugin with a built-in's name replaces it.

    Returns:
        App name mapped to its ``run(context)`` function.
    """
    from agentic_larp.apps import (  # noqa: PLC0415 - avoid an import cycle with the package
        _call,
        _deploy,
        _dropship,
        _hacker,
        _memecoin,
        _nft,
        _stonks,
        _wrapper,
    )

    apps: dict[str, App] = {
        "call": _call.run,
        "hacker": _hacker.run,
        "deploy": _deploy.run,
        "stonks": _stonks.run,
        "dropship": _dropship.run,
        "memecoin": _memecoin.run,
        "wrapper": _wrapper.run,
        "nft": _nft.run,
    }
    for entry_point in entry_points(group=ENTRY_POINT_GROUP):
        apps[entry_point.name] = entry_point.load()
    return apps
