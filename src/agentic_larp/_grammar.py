"""Tracery-like generative grammars and the activity scripts they produce."""

import math
import random
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass

from agentic_larp._errors import GrammarError
from agentic_larp._log import LogLine
from agentic_larp._policies import ChoicePolicy, RandomPolicy

REQUIRED_SYMBOLS = ("action", "quip", "final", "intern_task")
BOUND_SYMBOLS = ("file", "area", "agent", "intern", "n")

_REFERENCE = re.compile(r"#([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)#")
_NAME = re.compile(r"[A-Za-z_]\w*")
_TAGGED = re.compile(r"^(\w+):\s?(.*)$")
_TOOL = re.compile(r"^([A-Za-z]\w*)\((.*)\)$")
_DEFAULT_DEPTH = 32
_DIFF_SIGNS = {"add": "+", "del": "-"}
_RESULT_STYLES = {"ok": "green", "fail": "red", "note": "dim"}


def _camel(word: str) -> str:
    return "".join(part[:1].upper() + part[1:] for part in word.split("_"))


_MODIFIERS: dict[str, Callable[[str], str]] = {
    "capitalize": lambda word: word[:1].upper() + word[1:],
    "camel": _camel,
    "upper": str.upper,
}


def _parse_alternatives(name: str, value: object) -> tuple[tuple[str, float], ...]:
    must_be_text = f"{name!r} must be text"
    if _NAME.fullmatch(name) is None:
        message = f"{name!r} is not a valid symbol name"
        raise GrammarError(message)
    if isinstance(value, str):
        return ((value, 1.0),)
    if not isinstance(value, list):
        raise GrammarError(must_be_text)
    if not value:
        message = f"{name!r} has no alternatives"
        raise GrammarError(message)
    alternatives: list[tuple[str, float]] = []
    for item in value:
        if isinstance(item, str):
            alternatives.append((item, 1.0))
        elif isinstance(item, Mapping) and isinstance(item.get("text"), str):
            weight = item.get("weight", 1.0)
            if isinstance(weight, bool) or not isinstance(weight, (int, float)):
                message = f"{name!r} has a weight that is not a number"
                raise GrammarError(message)
            if not math.isfinite(weight):
                message = f"{name!r} has a weight that is not finite"
                raise GrammarError(message)
            if weight <= 0:
                message = f"{name!r} has a weight that is not positive"
                raise GrammarError(message)
            alternatives.append((item["text"], float(weight)))
        else:
            raise GrammarError(must_be_text)
    return tuple(alternatives)


@dataclass(frozen=True, slots=True)
class _Expansion:
    rng: random.Random
    bindings: Mapping[str, str]
    max_depth: int
    policy: ChoicePolicy


@dataclass(frozen=True, slots=True)
class Grammar:
    """Symbols mapped to weighted text alternatives.

    Text refers to other symbols as ``#name#``, optionally with modifiers
    such as ``#name.camel#``.

    Attributes:
        rules: Symbol mapped to its ``(text, weight)`` alternatives.
    """

    rules: Mapping[str, tuple[tuple[str, float], ...]]

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> "Grammar":
        """Build a grammar from parsed TOML or any plain mapping.

        Malformed input raises :class:`GrammarError`: a name that is not a
        valid symbol, a value that is not text, a rule with no alternatives,
        or a weight that is not a positive, finite number.

        Args:
            data: Symbol mapped to a string, a list of strings, or a list that
                mixes strings with ``{text=..., weight=...}`` tables.

        Returns:
            The grammar.
        """
        return cls({name: _parse_alternatives(name, v) for name, v in data.items()})

    def merge(self, override: "Grammar") -> "Grammar":
        """Layer another grammar on top of this one.

        Args:
            override: Grammar whose same-named rules replace this one's.

        Returns:
            A new grammar; neither input changes.
        """
        return Grammar({**self.rules, **override.rules})

    def check(self, *, required: Iterable[str], bound: Iterable[str]) -> None:
        """Verify that every reference resolves and required rules exist.

        Args:
            required: Symbols that must have a rule.
            bound: Names supplied at expansion time instead of by rules.

        Raises:
            GrammarError: If a rule shadows a bound name, a reference uses an
                unknown modifier or is undefined, or a required rule is
                missing.
        """
        bound_names = set(bound)
        shadowed = sorted(set(self.rules) & bound_names)
        if shadowed:
            message = f"rule {shadowed[0]!r} is filled in by agentic-larp"
            raise GrammarError(message)
        for alternatives in self.rules.values():
            for text, _ in alternatives:
                for match in _REFERENCE.finditer(text):
                    for modifier in match.group(1).split(".")[1:]:
                        if modifier not in _MODIFIERS:
                            message = f"unknown modifier {modifier!r}"
                            raise GrammarError(message)
        known = set(self.rules) | bound_names
        used = {
            match.group(1).split(".")[0]
            for alternatives in self.rules.values()
            for text, _ in alternatives
            for match in _REFERENCE.finditer(text)
        }
        if used - known:
            message = f"undefined symbols: {', '.join(sorted(used - known))}"
            raise GrammarError(message)
        missing = set(required) - set(self.rules)
        if missing:
            message = f"missing required symbols: {', '.join(sorted(missing))}"
            raise GrammarError(message)

    def expand(
        self,
        symbol: str,
        rng: random.Random,
        bindings: Mapping[str, str] | None = None,
        *,
        max_depth: int = _DEFAULT_DEPTH,
        policy: ChoicePolicy | None = None,
    ) -> str:
        """Generate text from a symbol.

        An unknown symbol or modifier, or a chain of rules expanding other
        rules more than ``max_depth`` deep, raises :class:`GrammarError`.

        Args:
            symbol: The rule to start from.
            rng: Random source; the same seed gives the same text.
            bindings: Values that win over rules for references.
            max_depth: The deepest allowed chain of rules expanding other
                rules.
            policy: Chooses among alternatives for every rule in the
                expansion; defaults to a fresh :class:`RandomPolicy`.

        Returns:
            The expanded text.
        """
        state = _Expansion(rng, bindings or {}, max_depth, policy or RandomPolicy())
        return self._expand(symbol, state, 0)

    def _expand(self, symbol: str, state: "_Expansion", depth: int) -> str:
        max_depth, bindings = state.max_depth, state.bindings
        if depth > max_depth:
            message = f"rules nest too deep (over {max_depth}) at {symbol!r}"
            raise GrammarError(message)
        alternatives = self.rules.get(symbol)
        if alternatives is None:
            message = f"unknown symbol {symbol!r}"
            raise GrammarError(message)
        index = state.policy.choose(symbol, alternatives, state.rng)
        if not isinstance(index, int) or not 0 <= index < len(alternatives):
            message = (
                f"policy returned {index!r}, which is not one of the "
                f"{len(alternatives)} alternatives of {symbol!r}"
            )
            raise GrammarError(message)
        text = alternatives[index][0]

        def resolve(match: re.Match[str]) -> str:
            name, *modifiers = match.group(1).split(".")
            if name in bindings:
                value = bindings[name]
            else:
                value = self._expand(name, state, depth + 1)
            for modifier in modifiers:
                if modifier not in _MODIFIERS:
                    message = f"unknown modifier {modifier!r}"
                    raise GrammarError(message)
                value = _MODIFIERS[modifier](value)
            return value

        return _REFERENCE.sub(resolve, text)


def parse_activity(text: str, first_line: int = 1) -> list[LogLine]:
    """Turn a tagged activity script into log lines.

    Tags are ``tool: Name(arg)``, ``add:``, ``del:``, ``ok:``, ``fail:``,
    ``note:``, and ``say:``.

    Args:
        text: One tagged line per row; blank lines are ignored.
        first_line: Line number of the first diff line; later ones count up.

    Returns:
        One log line per non-blank row.

    Raises:
        GrammarError: If a row has an unknown tag or a malformed ``tool:``.
    """
    lines: list[LogLine] = []
    number = first_line
    for raw in text.splitlines():
        row = raw.strip()
        if not row:
            continue
        tagged = _TAGGED.match(row)
        if tagged is None:
            message = f"unknown tag in {row!r}"
            raise GrammarError(message)
        tag, rest = tagged.groups()
        if tag == "tool":
            tool = _TOOL.match(rest)
            if tool is None:
                message = f"tool: lines look like Name(argument), not {rest!r}"
                raise GrammarError(message)
            lines.append(LogLine("tool", tool.group(2), tool.group(1)))
        elif tag in _DIFF_SIGNS:
            lines.append(LogLine("diff", rest, _DIFF_SIGNS[tag], number))
            number += 1
        elif tag in _RESULT_STYLES:
            lines.append(LogLine("result", rest, _RESULT_STYLES[tag]))
        elif tag == "say":
            lines.append(LogLine("quip", rest))
        else:
            message = f"unknown tag {tag!r}"
            raise GrammarError(message)
    return lines
