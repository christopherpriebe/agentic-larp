"""Drawing helpers shared by the wall and its widgets."""

from collections.abc import Iterator

from rich.console import Console, ConsoleOptions
from rich.text import Text

from agentic_larp._log import LogLine
from agentic_larp._sim import AgentView

SPINNER = "·✢✳✶✻✽✻✶✳✢"
ACCENT = "#e8875b"
BORDER = "#3a4a5a"
_DIFF_STYLES = {"-": "white on #7a1f1f", "+": "white on #1f6b2c"}
PANEL_MIN_HEIGHT = 7


def spinner(now: float, offset: float = 0.0) -> str:
    """Return the spinner frame for a moment in time.

    Args:
        now: Seconds since start.
        offset: Phase shift, so neighbouring spinners don't move in lockstep.

    Returns:
        One character.
    """
    return SPINNER[int((now + offset) * 10) % len(SPINNER)]


def render_entry(entry: LogLine, width: int) -> Text:
    """Render one log line at exactly the given width.

    Args:
        entry: A line from an agent's log.
        width: Cells available.

    Returns:
        A single, padded line.
    """
    if entry.kind == "tool":
        line = Text.assemble(
            ("● ", "green"),
            (entry.label, "bold"),
            ("(", "dim"),
            entry.text,
            (")", "dim"),
        )
    elif entry.kind == "diff":
        line = Text(
            f"{entry.number:>3} {entry.label} {entry.text}",
            style=_DIFF_STYLES[entry.label],
        )
    elif entry.kind == "result":
        line = Text.assemble(("  ⎿  ", "dim"), (entry.text, entry.label))
    elif entry.kind == "done":
        line = Text(entry.text, style="bold green")
    else:
        line = Text(entry.text, style="bold white")
    line.no_wrap = True
    line.truncate(width, overflow="ellipsis", pad=True)
    return line


class AgentBody:
    """The tail of an agent's log, one line per entry, fitted to its panel."""

    def __init__(self, agent: AgentView) -> None:
        self.agent = agent

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> Iterator[Text]:
        height = options.height or PANEL_MIN_HEIGHT
        entries = list(self.agent.log)[-height:]
        lines = [Text("")] * (height - len(entries))
        lines += [render_entry(entry, options.max_width) for entry in entries]
        yield Text("\n", no_wrap=True).join(lines)
