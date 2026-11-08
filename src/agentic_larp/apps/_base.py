"""What every payoff app shares: its context, the screen protocol, and the loop."""

import importlib
import pkgutil
import random
import time
from collections.abc import Callable, Mapping
from contextlib import nullcontext
from dataclasses import dataclass, field
from typing import Protocol, cast

from rich.console import Console, RenderableType
from rich.live import Live

from agentic_larp._errors import LarpError
from agentic_larp._keys import Keys, KeySource
from agentic_larp._plugins import load_registry

APP_ENTRY_POINT_GROUP = "agentic_larp.apps"
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
        rng: Random source for anything the app picks at random.
        flags: Free-form session state; ``ending=meltdown`` dooms the app.
    """

    console: Console
    task: str
    auto: float | None = None
    fps: int = 20
    keys: KeySource | None = None
    rng: random.Random = field(default_factory=random.Random)
    flags: Mapping[str, str] = field(default_factory=dict)


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


@dataclass(frozen=True, slots=True)
class App:
    """A payoff app: its name, a one-line description, and how to run it.

    Attributes:
        name: What ``--app`` and ``--play`` call it.
        description: One line for ``--list``.
        run: Launches the app.

    Raises:
        LarpError: If the name is blank.
    """

    name: str
    description: str
    run: Callable[[AppContext], None]

    def __post_init__(self) -> None:
        if not self.name.strip():
            message = "an app needs a name"
            raise LarpError(message)

    def __call__(self, context: AppContext) -> None:
        self.run(context)


def run_frames(
    screen: Screen,
    source: KeySource,
    fps: int,
    update: Callable[[RenderableType], None],
    auto: float | None = None,
) -> None:
    """Run the frame loop: keys, tick, draw, sleep, until the screen exits.

    Args:
        screen: The screen to feed keys and time to.
        source: Where keypresses come from.
        fps: Frames per second.
        update: Draws one rendered frame.
        auto: Stop after this many seconds (demo mode), or never.
    """
    start = last = time.monotonic()
    while True:
        if not all(screen.on_key(key) for key in source.read()):
            return
        now = time.monotonic()
        if not screen.tick(min(_MAX_DT, now - last)):
            return
        last = now
        if auto is not None and now - start > auto:
            return
        update(screen.render())
        time.sleep(max(0.0, 1 / fps - (time.monotonic() - now)))


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
        run_frames(
            screen,
            source,
            context.fps,
            lambda frame: live.update(frame, refresh=True),
            context.auto,
        )


def discover_apps(package: str = "agentic_larp.apps") -> dict[str, App]:
    """Find every app in a package: each module-level ``APP`` of its modules.

    Every module of the package is imported, underscore-named ones included;
    modules without an ``APP`` are ignored.

    Args:
        package: Dotted name of the package to scan.

    Returns:
        App name mapped to the app, sorted by name.

    Raises:
        LarpError: If the package is a plain module, or two modules define
            an app with the same name.
    """
    found: dict[str, App] = {}
    owners: dict[str, str] = {}
    path = getattr(importlib.import_module(package), "__path__", None)
    if path is None:
        message = f"{package!r} is not a package"
        raise LarpError(message)
    for info in pkgutil.iter_modules(path):
        module_name = f"{package}.{info.name}"
        app = getattr(importlib.import_module(module_name), "APP", None)
        if not isinstance(app, App):
            continue
        if app.name in found:
            message = (
                f"app {app.name!r} is defined by {owners[app.name]} and {module_name}"
            )
            raise LarpError(message)
        found[app.name] = app
        owners[app.name] = module_name
    return dict(sorted(found.items()))


def _check_app(name: str, value: object) -> App:
    if isinstance(value, App):
        return value
    if callable(value):
        return App(name, "plugin", cast("Callable[[AppContext], None]", value))
    message = f"{name!r} is neither an App nor a function"
    raise LarpError(message)


def app_registry(
    on_error: Callable[[str, Exception], None] | None = None,
) -> dict[str, App]:
    """Return every app by name: the built-ins, then installed plugins.

    Plugins register under the ``agentic_larp.apps`` entry-point group, as an
    :class:`App` or a bare ``run(context)`` function. A plugin with a
    built-in's name replaces it.

    Args:
        on_error: Called with the plugin name and the error for each plugin
            that fails to load or is rejected, which is then skipped. By
            default a failing plugin raises ``LarpError`` naming the group
            and plugin.

    Returns:
        App name mapped to the app. For a plugin the key is the entry-point
        name, even if an :class:`App` plugin carries another ``name``.
    """
    return load_registry(
        APP_ENTRY_POINT_GROUP, discover_apps(), check=_check_app, on_error=on_error
    )
