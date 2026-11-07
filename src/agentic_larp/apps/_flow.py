"""The shared shape of an app that can break: play, melt down, say goodbye."""

from collections import deque
from collections.abc import Sequence
from dataclasses import replace
from typing import Protocol

from agentic_larp.apps._base import AppContext, Outcome, Screen, run_loop
from agentic_larp.apps._meltdown import run_meltdown

BREAK_AT = 6.0  # seconds of normal running before a failing app breaks
BREAK_SECONDS = 3.0  # how long the in-app failure beat lasts


def push_feed(feed: deque[tuple[str, str]], style: str, line: str) -> None:
    """Add a line to a feed unless it repeats the previous line.

    Args:
        feed: The feed of ``(style, line)`` pairs.
        style: Rich style for the line.
        line: The text to add.
    """
    if not feed or feed[-1][1] != line:
        feed.append((style, line))


class BreakableScreen(Screen, Protocol):
    """A screen that knows whether it broke."""

    @property
    def has_broken(self) -> bool:
        """Return whether the failure beat has started."""
        ...


def play(
    context: AppContext,
    screen: BreakableScreen,
    errors: Sequence[str],
    success: str,
    failure: str,
) -> None:
    """Run a screen, then melt down if it broke, else say the normal goodbye.

    Under a failing outcome ``auto`` is dropped, or demo mode would end the app
    before it breaks.

    Args:
        context: The app's context.
        screen: The app's screen.
        errors: App-flavored errors for the meltdown cascade.
        success: Goodbye line when the app did not break.
        failure: Goodbye line printed after the meltdown.
    """
    is_failing = context.outcome is Outcome.FAIL
    run_loop(replace(context, auto=None) if is_failing else context, screen)
    if screen.has_broken:
        run_meltdown(context, screen.render(), errors)
        context.console.print(failure)
    else:
        context.console.print(success)
