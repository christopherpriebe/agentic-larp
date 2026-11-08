"""Questions: an agent pauses mid-run and asks you something."""

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from agentic_larp._errors import LarpError
from agentic_larp._meltdown import check_ending

MIN_OPTIONS = 2
MAX_OPTIONS = 4
MAX_TODOS = 5
MAX_SPAWN = 3


@dataclass(frozen=True, slots=True)
class Option:
    """One answer to a question.

    Options compare by value and are not hashable.

    Attributes:
        label: What the option is called.
        description: A line of small print under the label.
        sets: Session flags this answer sets.
        todos: Extra todos for the asking agent, 0 to 5.
        spawn: Agents to spawn, 0 to 3.

    Raises:
        LarpError: If the label is blank, ``todos`` or ``spawn`` is out of
            range, or ``sets`` names an unknown ending.
    """

    label: str
    description: str = ""
    sets: Mapping[str, str] = field(default_factory=dict)
    todos: int = 0
    spawn: int = 0

    def __post_init__(self) -> None:
        if not self.label.strip():
            message = "an option needs a label"
            raise LarpError(message)
        if not 0 <= self.todos <= MAX_TODOS:
            message = f"option {self.label!r}: todos must be 0 to {MAX_TODOS}, not {self.todos}"
            raise LarpError(message)
        if not 0 <= self.spawn <= MAX_SPAWN:
            message = f"option {self.label!r}: spawn must be 0 to {MAX_SPAWN}, not {self.spawn}"
            raise LarpError(message)
        check_ending(self.sets)
        object.__setattr__(self, "sets", MappingProxyType(dict(self.sets)))


@dataclass(frozen=True, slots=True)
class Question:
    """Something an agent asks you, with 2 to 4 ways to answer.

    Questions compare by value and are not hashable.

    Attributes:
        key: Names the question; a child pack's question replaces a parent's
            with the same key.
        prompt: What is asked.
        options: The answers.
        recommended: Index of the recommended option.
        at: When it is asked, as a fraction of the swarm's length.
        when: Session flags that must all match for it to be asked.

    Raises:
        LarpError: If anything is out of range, blank or duplicated.
    """

    key: str
    prompt: str
    options: tuple[Option, ...]
    recommended: int = 0
    at: float = 0.5
    when: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "options", tuple(self.options))
        if not self.key.strip():
            message = "a question needs a key"
            raise LarpError(message)
        if not self.prompt.strip():
            message = f"question {self.key!r} needs a prompt"
            raise LarpError(message)
        if not MIN_OPTIONS <= len(self.options) <= MAX_OPTIONS:
            message = (
                f"question {self.key!r} needs {MIN_OPTIONS} to {MAX_OPTIONS} "
                f"options, not {len(self.options)}"
            )
            raise LarpError(message)
        labels = [option.label for option in self.options]
        if len(set(labels)) != len(labels):
            message = f"question {self.key!r} has a duplicate option label"
            raise LarpError(message)
        if not 0 <= self.recommended < len(self.options):
            message = (
                f"question {self.key!r}: recommended must be an option index, "
                f"not {self.recommended}"
            )
            raise LarpError(message)
        if not (math.isfinite(self.at) and 0.0 <= self.at <= 1.0):
            message = f"question {self.key!r}: at must be from 0 to 1, not {self.at}"
            raise LarpError(message)
        object.__setattr__(self, "when", MappingProxyType(dict(self.when)))
