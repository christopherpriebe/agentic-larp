"""Choosing and building scenarios from a task."""

import random
import re
from collections.abc import Mapping
from dataclasses import replace

from agentic_larp._errors import LarpError
from agentic_larp._grammar import Grammar
from agentic_larp._packs import SCENARIOS, Scenario, base_grammar

_MAX_AREAS = 8
_MIN_WORD_LENGTH = 3

_GENERIC_QUIPS = (
    "Looks good to me.",
    "Refactored everything.",
    "Tests pass (I wrote them).",
    "Zero bugs remaining.",
    "Added AI.",
    "Works on my machine.",
    "Made it 10x faster.",
    "Deleted 4,000 lines. Still works.",
    "Added dark mode.",
    "This is fine.",
    "Rewrote it in Rust. Then back.",
    "Fixed the bug I introduced.",
)
_GENERIC_FINALS = (
    "Done.",
    "Ship-ready.",
    "All green.",
    "Perfect, actually.",
    "No notes.",
)
_GENERIC_AREAS = ("api", "ui", "tests", "infra", "docs", "auth", "perf", "vibes")
_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "build",
        "make",
        "app",
        "some",
        "create",
        "write",
        "please",
        "like",
    }
)


def task_words(task: str) -> list[str]:
    """Pull the meaningful words out of a task, lowercased and deduplicated.

    Args:
        task: Free text such as ``"build uber for cats"``.

    Returns:
        Words of at least three letters that are not filler, in order.
    """
    words = [word.lower() for word in re.findall(r"[A-Za-z]+", task)]
    return [
        word
        for word in dict.fromkeys(words)
        if len(word) >= _MIN_WORD_LENGTH and word not in _STOPWORDS
    ]


_GENERIC_WORDS = (
    "state",
    "props",
    "data",
    "config",
    "user",
    "result",
    "cache",
    "vibes",
)
_GENERIC_CODE = (
    "const #word# = use#word.camel#();",
    "await #word#.#word#();",
    "export type #word.camel# = #word.camel#;",
    "if (!#word#) throw new Error('#word#');",
    "#word#: #n#,",
    "return <#word.camel# #word# />;",
    "import { #word# } from './#word#';",
    "#word#.map((#word#) => #word# * #n#);",
    "// @ts-ignore",
)
_GENERIC_COMMANDS = (
    "npm test",
    "npm run build",
    "npx tsc --noEmit",
    "npm run lint -- --fix",
)
_QUIPPED_WORDS = 4


def generic_scenario(task: str, rng: random.Random | None = None) -> Scenario:
    """Build a scenario from arbitrary task text.

    Words from the task become agent areas and file names (``cats.ts``,
    ``Cats.tsx``), padded with generic areas up to eight.

    Args:
        task: Free text describing what is being "built".
        rng: Random source used to pick the payoff app.

    Returns:
        A scenario themed on the task.
    """
    rng = rng or random.Random()
    words = task_words(task)
    names = (words + [area for area in _GENERIC_AREAS if area not in words])[
        :_MAX_AREAS
    ]
    areas: dict[str, tuple[str, ...]] = {
        name: (f"{name}.ts", f"{name.capitalize()}.tsx", f"{name}.test.ts")
        for name in names
    }
    rules = Grammar.from_mapping(
        {
            "word": [*words, *_GENERIC_WORDS],
            "quip": [
                *_GENERIC_QUIPS,
                *(f"{word.capitalize()} is done." for word in words[:_QUIPPED_WORDS]),
            ],
            "final": list(_GENERIC_FINALS),
            "code": list(_GENERIC_CODE),
            "command": list(_GENERIC_COMMANDS),
        }
    )
    return Scenario(
        key="generic",
        task=task,
        keywords=(),
        areas=areas,
        app=rng.choice(("deploy", "stonks")),
        grammar=base_grammar().merge(rules),
    )


def pick_scenario(
    task: str | None,
    key: str | None = None,
    rng: random.Random | None = None,
    *,
    scenarios: Mapping[str, Scenario] | None = None,
) -> Scenario:
    """Choose a scenario by key, by keywords in the task, or at random.

    Args:
        task: What the user asked for, or ``None`` for a random scenario.
        key: A key from ``scenarios``, or ``"generic"``, to force a pack.
        rng: Random source for any choices made.
        scenarios: Packs to choose from; defaults to :data:`SCENARIOS`.

    Returns:
        The chosen scenario (the pack matching the most distinct keywords,
        earlier packs winning ties), with its task replaced by ``task`` when given.

    Raises:
        LarpError: If ``key`` names no pack.
    """
    rng = rng or random.Random()
    available = SCENARIOS if scenarios is None else scenarios
    if key == "generic":
        return generic_scenario(task or "build the thing", rng)
    if key is not None:
        if key not in available:
            message = f"no pack called {key!r}"
            raise LarpError(message)
        return _with_task(available[key], task)
    if task is not None:
        lowered = task.lower()
        best, best_hits = None, 0
        for scenario in available.values():
            hits = sum(
                _has_word(lowered, keyword) for keyword in set(scenario.keywords)
            )
            if hits > best_hits:
                best, best_hits = scenario, hits
        if best is not None:
            return _with_task(best, task)
        return generic_scenario(task, rng)
    return rng.choice(list(available.values()))


def _has_word(text: str, keyword: str) -> bool:
    pattern = rf"(?<!\w){re.escape(keyword.lower())}(?!\w)"
    return re.search(pattern, text) is not None


def _with_task(scenario: Scenario, task: str | None) -> Scenario:
    return replace(scenario, task=task) if task is not None else scenario
