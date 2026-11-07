"""The unit of fake agent output."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LogLine:
    """One line in an agent's panel.

    Attributes:
        kind: ``"tool"``, ``"diff"``, ``"result"``, ``"quip"``, or ``"done"``.
        text: The tool argument, code, or message.
        label: The tool name, the diff sign, or the result style.
        number: The line number of a diff line.
    """

    kind: str
    text: str
    label: str = ""
    number: int = 0
