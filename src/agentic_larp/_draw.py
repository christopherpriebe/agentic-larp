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


_TOOL_NAMES = {"Edit": "Update", "Grep": "Search", "WebSearch": "Web Search"}


def _tool_argument(entry: LogLine) -> str:
    if entry.label == "Grep":
        return f'pattern: "{entry.text}"'
    if entry.label == "WebSearch":
        return f'"{entry.text}"'
    return entry.text


def render_entry(
    entry: LogLine, width: int, *, continued: bool = False, failed: bool = False
) -> Text:
    """Render one log line at exactly the given width.

    Args:
        entry: A line from an agent's log.
        width: Cells available.
        continued: Whether a result follows other output, so it hangs under
            the first line instead of getting its own ``⎿`` marker.
        failed: Whether a tool call's bullet is red because it failed.

    Returns:
        A single, padded line.
    """
    if entry.kind == "tool":
        name = _TOOL_NAMES.get(entry.label, entry.label)
        line = Text.assemble(("● ", "red" if failed else "green"), (name, "bold"))
        if entry.text:
            line.append("(", style="dim")
            line.append(_tool_argument(entry))
            line.append(")", style="dim")
    elif entry.kind == "diff":
        line = Text(
            f"     {entry.number:>4} {entry.label} {entry.text}",
            style=_DIFF_STYLES.get(entry.label, "dim"),
        )
    elif entry.kind == "result":
        prefix = "     " if continued else "  ⎿  "
        line = Text.assemble((prefix, "dim"), (entry.text, entry.label))
    elif entry.kind == "done":
        line = Text(entry.text, style="bold green")
    else:
        line = Text.assemble(("● ", "white"), entry.text)
    line.no_wrap = True
    line.truncate(width, overflow="ellipsis", pad=True)
    return line


def _has_failed(entries: list[LogLine], index: int) -> bool:
    for entry in entries[index + 1 :]:
        if entry.kind in {"tool", "quip", "done"}:
            return False
        if entry.kind == "result" and entry.label == "red":
            return True
    return False


def _is_turn(entry: LogLine) -> bool:
    return entry.kind in {"tool", "quip", "done"}


class AgentBody:
    """The tail of an agent's log, fitted to its panel like a transcript."""

    def __init__(self, agent: AgentView) -> None:
        self.agent = agent

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> Iterator[Text]:
        height = options.height or PANEL_MIN_HEIGHT
        log = list(self.agent.log)
        rows: list[Text] = []
        for index in range(len(log)):
            entry = log[index]
            previous = log[index - 1] if index else None
            if _is_turn(entry) and index:
                rows.append(Text(""))
            rows.append(
                render_entry(
                    entry,
                    options.max_width,
                    continued=entry.kind == "result"
                    and previous is not None
                    and previous.kind in {"result", "diff"},
                    failed=entry.kind == "tool" and _has_failed(log, index),
                )
            )
        rows = rows[-height:]
        if len(rows) == height and not rows[0].plain.strip():
            rows = [*rows[1:], Text("")]
        lines = [Text("")] * (height - len(rows)) + rows
        yield Text("\n", no_wrap=True).join(lines)
