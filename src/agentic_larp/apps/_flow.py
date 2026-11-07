"""Shared pieces of an app that can break: timing and the feed."""

from collections import deque

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
