"""Chart and ticker helpers shared by the market apps."""

import re

from rich.text import Text

_MIN_WORD_LENGTH = 3
_TICKER_LETTERS = 4


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
