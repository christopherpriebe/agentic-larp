"""Pack files: scenarios described in TOML on top of a shared base grammar."""

import os
import random
import tomllib
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

from agentic_larp._errors import GrammarError
from agentic_larp._grammar import (
    BOUND_SYMBOLS,
    REQUIRED_SYMBOLS,
    Grammar,
    parse_activity,
)

_BUILTIN_PACKS = (
    "girlfriend",
    "startup",
    "hacker",
    "prod",
    "dropship",
    "memecoin",
    "wrapper",
    "nft",
)
_DEFAULT_APP = "deploy"
_RESERVED_KEY = "generic"
_SMOKE_ACTIONS = 25
_SMOKE_OTHERS = 3
_SMOKE_SEED = 1


@dataclass(frozen=True, slots=True)
class Scenario:
    """A themed set of fake work for the agents.

    Attributes:
        key: Short name used on the command line (``-s key``).
        task: What the user asked for, shown in the header.
        keywords: Words in a task that select this scenario.
        areas: Agent area label mapped to the files that agent touches.
        app: Name of the app launched after shipping.
        grammar: Everything the agents say and do, as rules.
        area_rules: Per-area rules that replace same-named rules in ``grammar``.
    """

    key: str
    task: str
    keywords: tuple[str, ...]
    areas: dict[str, tuple[str, ...]]
    app: str
    grammar: Grammar
    area_rules: dict[str, Grammar] = field(default_factory=dict)

    def grammar_for(self, area: str) -> Grammar:
        """Return the grammar an agent working on an area uses.

        Args:
            area: One of :attr:`areas`.

        Returns:
            The scenario grammar with that area's overrides applied.
        """
        overrides = self.area_rules.get(area)
        return self.grammar if overrides is None else self.grammar.merge(overrides)


def _read_resource(name: str) -> str:
    return resources.files("agentic_larp").joinpath("packs", name).read_text("utf-8")


def base_grammar() -> Grammar:
    """Load the grammar every pack builds on.

    Returns:
        The packaged base grammar.
    """
    data = tomllib.loads(_read_resource("base.toml"))
    return Grammar.from_mapping(data)


def _fail(label: str, message: str) -> GrammarError:
    return GrammarError(f"{label}: {message}")


def _text_list(label: str, where: str, value: object) -> tuple[str, ...]:
    items = value if isinstance(value, list) else None
    names = [item for item in items or [] if isinstance(item, str)]
    if items is None or len(names) != len(items):
        raise _fail(label, f"{where} must be a list of file names")
    return tuple(names)


def _require_files(label: str, name: str, files: tuple[str, ...]) -> None:
    if not files:
        raise _fail(label, f"area {name!r} has no files")


def _parse_areas(
    label: str, raw_areas: dict[str, object]
) -> tuple[dict[str, tuple[str, ...]], dict[str, Grammar]]:
    areas: dict[str, tuple[str, ...]] = {}
    overrides: dict[str, Grammar] = {}
    for name, entry in raw_areas.items():
        if not isinstance(entry, dict):
            areas[name] = _text_list(label, f"areas.{name}", entry)
            _require_files(label, name, areas[name])
            continue
        areas[name] = _text_list(label, f"[areas.{name}] files", entry.get("files"))
        _require_files(label, name, areas[name])
        rules = entry.get("rules")
        if rules is None:
            continue
        if not isinstance(rules, dict):
            raise _fail(label, f"[areas.{name}] rules must be a table")
        overrides[name] = Grammar.from_mapping(rules)
    return areas, overrides


def _parse_scenario(text: str, label: str, base: Grammar) -> Scenario:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as err:
        raise _fail(label, f"not valid TOML ({err})") from err
    pack = data.get("pack")
    if not isinstance(pack, dict) or not isinstance(pack.get("key"), str):
        raise _fail(label, "missing [pack] key")
    if not isinstance(pack.get("task"), str):
        raise _fail(label, "missing [pack] task")
    raw_areas = data.get("areas")
    if pack["key"] == _RESERVED_KEY:
        raise _fail(
            label, f"{_RESERVED_KEY!r} is reserved for the built-in generic pack"
        )
    if not isinstance(pack.get("app", _DEFAULT_APP), str):
        raise _fail(label, "[pack] app must be text")
    if not isinstance(raw_areas, dict) or not raw_areas:
        raise _fail(label, "no [areas] (give at least one area with files)")
    try:
        areas, overrides = _parse_areas(label, raw_areas)
        extra = data.get("rules", {})
        if not isinstance(extra, dict):
            raise _fail(label, "[rules] must be a table")
        grammar = base.merge(Grammar.from_mapping(extra))
    except GrammarError as err:
        if str(err).startswith(f"{label}: "):
            raise
        raise _fail(label, str(err)) from err
    keywords = _text_list(label, "[pack] keywords", pack.get("keywords", []))
    if not all(keyword.strip() for keyword in keywords):
        raise _fail(label, "[pack] keywords has an empty keyword")
    keywords = tuple(keyword.strip() for keyword in keywords)
    scenario = Scenario(
        key=pack["key"],
        task=pack["task"],
        keywords=keywords,
        areas=areas,
        app=str(pack.get("app", _DEFAULT_APP)),
        grammar=grammar,
        area_rules=overrides,
    )
    try:
        _verify(scenario)
    except GrammarError as err:
        raise _fail(label, str(err)) from err
    return scenario


def _verify(scenario: Scenario) -> None:
    scenario.grammar.check(required=REQUIRED_SYMBOLS, bound=BOUND_SYMBOLS)
    rng = random.Random(_SMOKE_SEED)
    bindings = dict.fromkeys(BOUND_SYMBOLS, "x")
    for area in scenario.areas:
        grammar = scenario.grammar_for(area)
        grammar.check(required=REQUIRED_SYMBOLS, bound=BOUND_SYMBOLS)
        for _ in range(_SMOKE_ACTIONS):
            parse_activity(grammar.expand("action", rng, bindings))
        for symbol in ("quip", "final", "intern_task"):
            for _ in range(_SMOKE_OTHERS):
                grammar.expand(symbol, rng, bindings)


def load_scenario(path: Path, base: Grammar | None = None) -> Scenario:
    """Read a pack file.

    Args:
        path: A ``.toml`` pack.
        base: Grammar the pack's rules are layered over; defaults to
            :func:`base_grammar`.

    Returns:
        The scenario.

    Raises:
        GrammarError: If the file cannot be read or is not a valid pack. The
            message names the file.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as err:
        message = f"{path}: cannot read ({err})"
        raise GrammarError(message) from err
    return _parse_scenario(text, str(path), base or base_grammar())


def discover_scenarios(
    paths: Iterable[Path],
    *,
    on_error: Callable[[GrammarError], None] | None = None,
) -> dict[str, Scenario]:
    """Load packs from files and directories.

    Args:
        paths: Pack files, or directories whose ``*.toml`` files are loaded in
            sorted order. Missing paths are skipped; later packs replace
            earlier ones with the same key.
        on_error: Called with the error for each broken file, which is then
            skipped. By default the error is raised.

    Returns:
        Packs by key.

    Raises:
        GrammarError: If a file is broken and ``on_error`` is not given.
    """
    base = base_grammar()
    found: dict[str, Scenario] = {}
    for path in paths:
        if path.is_dir():
            files = sorted(path.glob("*.toml"))
        elif path.is_file() and path.suffix == ".toml":
            files = [path]
        else:
            continue
        for file in files:
            try:
                scenario = load_scenario(file, base)
            except GrammarError as err:
                if on_error is None:
                    raise
                on_error(err)
                continue
            found[scenario.key] = scenario
    return found


def default_pack_dirs() -> list[Path]:
    """Return the directories searched for user packs.

    Returns:
        ``$XDG_CONFIG_HOME/agentic-larp/packs``, or under ``~/.config``.
    """
    configured = os.environ.get("XDG_CONFIG_HOME")
    root = (
        Path(configured)
        if configured is not None and configured != ""
        else Path.home() / ".config"
    )
    return [root / "agentic-larp" / "packs"]


def _load_builtins() -> dict[str, Scenario]:
    base = base_grammar()
    scenarios = (
        _parse_scenario(_read_resource(f"{name}.toml"), f"{name}.toml", base)
        for name in _BUILTIN_PACKS
    )
    return {scenario.key: scenario for scenario in scenarios}


SCENARIOS: dict[str, Scenario] = _load_builtins()
