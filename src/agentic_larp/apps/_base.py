"""What every payoff app shares: its context, the screen protocol, and the loop."""

import time
from collections.abc import Callable
from contextlib import nullcontext
from dataclasses import dataclass
from importlib.metadata import entry_points
from typing import Protocol, TypeAlias

from rich.console import Console, RenderableType
from rich.live import Live

from agentic_larp._keys import Keys, KeySource

ENTRY_POINT_GROUP = "agentic_larp.apps"
_MAX_DT = 0.25


@dataclass(frozen=True, slots=True)
class AppContext:
    """Everything an app gets when it launches.

    Attributes:
        console: Where to draw.
        task: What the agents "built", for flavor text.
        auto: Exit on its own after this many seconds (demo mode), or never.
        fps: Frames per second.
        keys: Key source to read from; ``None`` reads the real keyboard.
    """

    console: Console
    task: str
    auto: float | None = None
    fps: int = 20
    keys: KeySource | None = None


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
    "hacker": "hacker typer: mash keys, look like a genius (tab = access granted)",
    "deploy": "a global prod rollout that definitely won't page anyone",
    "stonks": "your startup's stock, which only goes up",
}


def app_registry() -> dict[str, App]:
    """Return every app by name: the built-ins, then installed plugins.

    Plugins register under the ``agentic_larp.apps`` entry-point group. A
    plugin with a built-in's name replaces it.

    Returns:
        App name mapped to its ``run(context)`` function.
    """
    from agentic_larp.apps import _call, _deploy, _hacker, _stonks  # noqa: PLC0415 - avoid an import cycle with the package

    apps: dict[str, App] = {
        "call": _call.run,
        "hacker": _hacker.run,
        "deploy": _deploy.run,
        "stonks": _stonks.run,
    }
    for entry_point in entry_points(group=ENTRY_POINT_GROUP):
        apps[entry_point.name] = entry_point.load()
    return apps
