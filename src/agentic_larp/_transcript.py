"""Reshape parsed activity into the form Claude Code prints it."""

from collections.abc import Iterable
from dataclasses import replace

from agentic_larp._log import LogLine

_FAILURE_MARK = "✗ "
_PANIC_MARKERS = ("panicked", "error[E")


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def _is_failure(line: LogLine) -> bool:
    return (
        line.kind == "result"
        and line.label == "red"
        and line.text.startswith(_FAILURE_MARK)
    )


def _summarize_edit(tool: LogLine, diffs: list[LogLine]) -> list[LogLine]:
    old = new = diffs[0].number
    renumbered: list[LogLine] = []
    for line in diffs:
        if line.label == "-":
            renumbered.append(replace(line, number=old))
            old += 1
        elif line.label == "+":
            renumbered.append(replace(line, number=new))
            new += 1
        else:
            renumbered.append(replace(line, number=new))
            old += 1
            new += 1
    added = sum(line.label == "+" for line in diffs)
    removed = sum(line.label == "-" for line in diffs)
    parts = []
    if added:
        parts.append(_plural(added, "addition"))
    if removed:
        parts.append(_plural(removed, "removal"))
    summary = LogLine(
        "result", f"Updated {tool.text} with {' and '.join(parts)}", "dim"
    )
    return [tool, summary, *renumbered]


def _fail(tool: LogLine, rest: list[LogLine]) -> list[LogLine]:
    if not any(_is_failure(line) for line in rest):
        return rest
    blob = " ".join(item.text for item in [tool, *rest])
    code = 101 if any(marker in blob for marker in _PANIC_MARKERS) else 1
    output: list[LogLine] = []
    is_first = True
    for line in rest:
        if not _is_failure(line):
            output.append(line)
            continue
        stripped = line.text.removeprefix(_FAILURE_MARK)
        if tool.label != "Bash":
            output.append(replace(line, text=f"Error: {stripped}"))
        else:
            if is_first:
                output.append(LogLine("result", f"Error: Exit code {code}", "red"))
            output.append(replace(line, text=stripped))
        is_first = False
    return output


def _reshape_block(tool: LogLine, body: list[LogLine]) -> list[LogLine]:
    diffs = [line for line in body if line.kind == "diff"]
    if tool.label == "Edit":
        failure = next((line for line in body if _is_failure(line)), None)
        if failure is not None:
            text = failure.text.removeprefix(_FAILURE_MARK)
            return [tool, replace(failure, text=f"Error: {text}")]
        is_summarized = any(
            line.kind == "result" and line.text.startswith(f"Updated {tool.text} with ")
            for line in body
        )
        if not is_summarized and any(line.label in {"+", "-"} for line in diffs):
            return _summarize_edit(tool, diffs)
        return [tool, *body]
    rest = _fail(tool, body)
    if tool.label == "Write":
        suffix = f" to {tool.text}"
        results = [
            replace(line, text=f"{line.text}{suffix}")
            if line.kind == "result"
            and line.text.startswith("Wrote ")
            and not line.text.endswith(suffix)
            else line
            for line in rest
            if line.kind != "diff"
        ]
        context = [
            replace(line, label=" ", number=number)
            for number, line in enumerate(
                (item for item in rest if item.kind == "diff"), start=1
            )
        ]
        return [tool, *results, *context]
    return [tool, *rest]


def as_transcript(lines: Iterable[LogLine]) -> list[LogLine]:
    """Reshape parsed activity the way Claude Code prints a session.

    Edits lead with an ``Updated ... with N additions`` summary and renumbered
    diffs, writes preview their lines as plain code, and failures report an
    exit code or a one-line error. Tool and quip lines keep their order;
    anything before the first tool passes through.

    Args:
        lines: Log lines, such as the output of ``parse_activity``.

    Returns:
        The reshaped lines.
    """
    output: list[LogLine] = []
    tool: LogLine | None = None
    body: list[LogLine] = []
    for line in lines:
        if line.kind in {"tool", "quip"}:
            if tool is not None:
                output.extend(_reshape_block(tool, body))
            body = []
            tool = line if line.kind == "tool" else None
            if tool is None:
                output.append(line)
        elif tool is None:
            output.append(line)
        else:
            body.append(line)
    if tool is not None:
        output.extend(_reshape_block(tool, body))
    return output
