"""Pack files: scenarios described in TOML on top of a shared base grammar."""

import os
import random
import tomllib
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from types import MappingProxyType

from agentic_larp._errors import GrammarError, LarpError
from agentic_larp._grammar import (
    BOUND_SYMBOLS,
    REQUIRED_SYMBOLS,
    Grammar,
    parse_activity,
)
from agentic_larp._questions import Option, Question

_BUILTIN_PACKS = (
    "girlfriend",
    "startup",
    "hacker",
    "prod",
    "dropship",
    "memecoin",
    "wrapper",
    "nft",
    "thoughtleader",
    "clipfarm",
    "matchmaker",
)
_BUILTIN_TOOLCHAINS = ("cpp", "typescript", "python", "rust")
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
        abstract: Whether this is a toolchain to extend, not a pack to run.
        parents: Keys of the packs this one extends, in order.
        questions: What the agents ask, in order.
        layer: Every rule this pack and its ancestors set or extended, so a
            child can layer them over its own base; rules only inherited from
            the base grammar are left out.
    """

    key: str
    task: str
    keywords: tuple[str, ...]
    areas: Mapping[str, tuple[str, ...]]
    app: str
    grammar: Grammar
    area_rules: Mapping[str, Grammar] = field(default_factory=dict)
    abstract: bool = False
    parents: tuple[str, ...] = ()
    layer: Grammar = field(default_factory=lambda: Grammar({}))
    questions: tuple[Question, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "areas", MappingProxyType(dict(self.areas)))
        object.__setattr__(self, "area_rules", MappingProxyType(dict(self.area_rules)))

    def grammar_for(self, area: str) -> Grammar:
        """Return the grammar an agent working on an area uses.

        Args:
            area: One of :attr:`areas`.

        Returns:
            The scenario grammar with that area's overrides applied.
        """
        overrides = self.area_rules.get(area)
        return self.grammar if overrides is None else self.grammar.merge(overrides)


def _read_resource(*parts: str) -> str:
    return resources.files("agentic_larp").joinpath("packs", *parts).read_text("utf-8")


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


def _extends(label: str, pack: dict[str, object]) -> tuple[str, ...]:
    raw = pack.get("extends", [])
    names = [raw] if isinstance(raw, str) else raw
    if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
        raise _fail(label, "[pack] extends must be a pack name or a list of names")
    return tuple(str(name) for name in names)


def _resolve_grammar(
    data: dict[str, object], base: Grammar, parents: list[Scenario]
) -> tuple[Grammar, Grammar]:
    # Returns the pack's (layer, resolved grammar).
    inherited = Grammar({})
    for parent in parents:
        inherited = inherited.merge(parent.layer)
    rules, extend = data.get("rules", {}), data.get("extend", {})
    if not isinstance(rules, dict):
        message = "[rules] must be a table"
        raise GrammarError(message)
    if not isinstance(extend, dict):
        message = "[extend] must be a table"
        raise GrammarError(message)
    layer = inherited.merge(Grammar.from_mapping(rules))
    resolved = base.merge(layer)
    for name, added in Grammar.from_mapping(extend).rules.items():
        grown = Grammar({name: (*resolved.rules.get(name, ()), *added)})
        layer, resolved = layer.merge(grown), resolved.merge(grown)
    return layer, resolved


def _read_pack(
    label: str, text: str
) -> tuple[dict[str, object], dict[str, object], str]:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as err:
        raise _fail(label, f"not valid TOML ({err})") from err
    pack: object = data.get("pack")
    key = pack.get("key") if isinstance(pack, dict) else None
    if not isinstance(pack, dict) or not isinstance(key, str):
        raise _fail(label, "missing [pack] key")
    if key == _RESERVED_KEY:
        raise _fail(
            label, f"{_RESERVED_KEY!r} is reserved for the built-in generic pack"
        )
    if not isinstance(pack.get("abstract", False), bool):
        raise _fail(label, "[pack] abstract must be true or false")
    for field_name in ("task", "app"):
        if not isinstance(pack.get(field_name, ""), str):
            raise _fail(label, f"[pack] {field_name} must be text")
    return dict(data), dict(pack), key


def _parse_scenario(
    text: str,
    label: str,
    base: Grammar,
    packs: Mapping[str, Scenario],
    *,
    is_trusted: bool = False,
) -> Scenario:
    data, pack, key = _read_pack(label, text)
    is_abstract = bool(pack.get("abstract", False))
    names = _extends(label, pack)
    parents = [_parent(label, name, packs) for name in names]
    task = str(pack.get("task", "")) or _first_inherited(parents, "task")
    if not task and not is_abstract:
        raise _fail(label, "missing [pack] task")
    app = str(pack.get("app", "")) or _first_inherited(parents, "app")
    try:
        areas, overrides = _own_areas(label, data.get("areas"))
        layer, grammar = _resolve_grammar(data, base, parents)
    except GrammarError as err:
        if str(err).startswith(f"{label}: "):
            raise
        raise _fail(label, str(err)) from err
    donor = _last_with_areas(parents)
    if not areas and donor is not None:
        areas, overrides = dict(donor.areas), dict(donor.area_rules)
    if not areas and not is_abstract:
        raise _fail(label, "no [areas] (give at least one area with files)")
    questions = _resolve_questions(label, data.get("questions"), parents)
    keywords = _text_list(label, "[pack] keywords", pack.get("keywords", []))
    if not all(keyword.strip() for keyword in keywords):
        raise _fail(label, "[pack] keywords has an empty keyword")
    scenario = Scenario(
        key=key,
        task=task,
        keywords=tuple(keyword.strip() for keyword in keywords),
        areas=areas,
        app=app or ("" if is_abstract else _DEFAULT_APP),
        grammar=grammar,
        area_rules=overrides,
        abstract=is_abstract,
        parents=names,
        layer=layer,
        questions=questions,
    )
    # Built-in packs are smoke-checked by the test suite, not on every startup.
    if not is_abstract and not is_trusted:
        try:
            _verify(scenario)
        except GrammarError as err:
            raise _fail(label, str(err)) from err
    return scenario


def _text_table(label: str, where: str, value: object) -> dict[str, str]:
    if not isinstance(value, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in value.items()
    ):
        raise _fail(label, f"{where} must be a table of text")
    return dict(value)


def _small_int(label: str, where: str, value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise _fail(label, f"{where} must be a whole number")
    return value


def _text_field(label: str, where: str, table: dict[str, object], name: str) -> str:
    value = table.get(name, "" if name != "label" else None)
    if value is None:
        raise _fail(label, f"{where} needs a {name} (text)")
    if not isinstance(value, str):
        raise _fail(label, f"{where} {name} must be text")
    return value


def _parse_option(label: str, where: str, raw: object) -> Option:
    if not isinstance(raw, dict):
        raise _fail(label, f"{where} must be a table")
    sets = _text_table(label, f"{where} sets", raw.get("sets", {}))
    return Option(
        _text_field(label, where, raw, "label"),
        _text_field(label, where, raw, "description"),
        sets,
        _small_int(label, f"{where} todos", raw.get("todos", 0)),
        _small_int(label, f"{where} spawn", raw.get("spawn", 0)),
    )


def _parse_question(label: str, index: int, raw: object) -> Question:
    where = f"[[questions]] #{index + 1}"
    if not isinstance(raw, dict):
        raise _fail(label, f"{where} must be a table")
    key = raw.get("key")
    if not isinstance(key, str):
        raise _fail(label, f"{where} needs a key (text)")
    where = f"question {key!r}"
    prompt = raw.get("prompt")
    if not isinstance(prompt, str):
        raise _fail(label, f"{where} needs a prompt (text)")
    raw_options = raw.get("options")
    if not isinstance(raw_options, list):
        raise _fail(label, f"{where} needs [[questions.options]] tables")
    try:
        options = tuple(
            _parse_option(label, f"{where} option #{n + 1}", item)
            for n, item in enumerate(raw_options)
        )
    except GrammarError:
        raise
    except LarpError as err:
        raise _fail(label, f"{where}: {err}") from err
    at = raw.get("at", 0.5)
    if not isinstance(at, int | float) or isinstance(at, bool):
        raise _fail(label, f"{where} at must be a number")
    return Question(
        key,
        prompt,
        options,
        _small_int(label, f"{where} recommended", raw.get("recommended", 0)),
        float(at),
        _text_table(label, f"{where} when", raw.get("when", {})),
    )


def _resolve_questions(
    label: str, raw: object, parents: list[Scenario]
) -> tuple[Question, ...]:
    # A child's question replaces a parent's with the same key, in place.
    merged: dict[str, Question] = {}
    for parent in parents:
        merged.update((question.key, question) for question in parent.questions)
    if raw is None:
        return tuple(merged.values())
    if not isinstance(raw, list):
        raise _fail(label, "[[questions]] must be an array of tables")
    try:
        merged.update(
            (question.key, question)
            for question in (
                _parse_question(label, n, item) for n, item in enumerate(raw)
            )
        )
    except GrammarError:
        raise
    except LarpError as err:
        raise _fail(label, str(err)) from err
    return tuple(merged.values())


def _parent(label: str, name: str, packs: Mapping[str, Scenario]) -> Scenario:
    if name not in packs:
        raise _fail(label, f"unknown parent {name!r}")
    return packs[name]


def _own_areas(
    label: str, raw: object
) -> tuple[dict[str, tuple[str, ...]], dict[str, Grammar]]:
    if raw is None:
        return {}, {}
    if not isinstance(raw, dict):
        raise _fail(label, "[areas] must be a table")
    return _parse_areas(label, raw)


def _first_inherited(parents: list[Scenario], attribute: str) -> str:
    for parent in reversed(parents):
        value = getattr(parent, attribute)
        if value:
            return str(value)
    return ""


def _last_with_areas(parents: list[Scenario]) -> Scenario | None:
    return next((parent for parent in reversed(parents) if parent.areas), None)


def _verify(scenario: Scenario) -> None:
    scenario.grammar.check(required=REQUIRED_SYMBOLS, bound=BOUND_SYMBOLS)
    rng = random.Random(_SMOKE_SEED)
    bindings = dict.fromkeys(BOUND_SYMBOLS, "x")
    for area in scenario.areas:
        grammar = scenario.grammar_for(area)
        grammar.check(required=REQUIRED_SYMBOLS, bound=BOUND_SYMBOLS)
        for _ in range(_SMOKE_ACTIONS):
            parse_activity(grammar.expand("action", rng, bindings))
        for symbol in ("quip", "final", "intern_task", "todo"):
            for _ in range(_SMOKE_OTHERS):
                grammar.expand(symbol, rng, bindings)


def load_scenario(
    path: Path,
    base: Grammar | None = None,
    *,
    packs: Mapping[str, Scenario] | None = None,
) -> Scenario:
    """Read a pack file.

    Args:
        path: A ``.toml`` pack.
        base: Grammar the pack's rules are layered over; defaults to
            :func:`base_grammar`.
        packs: Packs its ``extends`` names resolve against; defaults to every
            built-in toolchain and pack.

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
    known = {**TOOLCHAINS, **SCENARIOS} if packs is None else packs
    return _parse_scenario(text, str(path), base or base_grammar(), known)


def _pack_files(paths: Iterable[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files.extend(sorted(path.glob("*.toml")))
        elif path.is_file() and path.suffix == ".toml":
            files.append(path)
    return files


def _peek(file: Path) -> tuple[str, tuple[str, ...]] | None:
    """Return a pack file's (key, extends), or None if it can't be read yet."""
    try:
        pack = tomllib.loads(file.read_text(encoding="utf-8")).get("pack")
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return None
    key = pack.get("key") if isinstance(pack, dict) else None
    if not isinstance(pack, dict) or not isinstance(key, str):
        return None
    raw = pack.get("extends", [])
    names = [raw] if isinstance(raw, str) else raw
    if not isinstance(names, list):
        return None
    return key, tuple(name for name in names if isinstance(name, str))


def discover_scenarios(
    paths: Iterable[Path],
    *,
    on_error: Callable[[GrammarError], None] | None = None,
) -> dict[str, Scenario]:
    """Load packs from files and directories.

    Packs are loaded parents first, whatever the file order; parents come
    from the same discovery or from the built-ins. Abstract packs are
    returned too.

    Args:
        paths: Pack files, or directories whose ``*.toml`` files are loaded in
            sorted order. Missing paths are skipped; later packs replace
            earlier ones with the same key.
        on_error: Called with the error for each broken file (or inheritance
            cycle), which is then skipped. By default a :class:`GrammarError`
            is raised instead.

    Returns:
        Packs by key.
    """
    base = base_grammar()
    found: dict[str, Scenario] = {}
    pending: dict[str, tuple[Path, tuple[str, ...]]] = {}
    unordered: list[Path] = []
    for file in _pack_files(paths):
        peeked = _peek(file)
        if peeked is None:
            unordered.append(file)
        else:
            pending[peeked[0]] = (file, peeked[1])

    failed: set[str] = set()
    unreadable: set[str] = set()  # stems of files whose key is unknown

    def report(error: GrammarError) -> None:
        if on_error is None:
            raise error
        on_error(error)

    def load(file: Path) -> None:
        known = {**TOOLCHAINS, **SCENARIOS, **found}
        scenario = load_scenario(file, base, packs=known)
        found[scenario.key] = scenario

    def visit(key: str, stack: tuple[str, ...]) -> None:
        if key in found or key in failed:
            return
        file, parents = pending[key]
        if key in stack:
            circle = " -> ".join(pending[k][0].name for k in (*stack, key))
            failed.update((*stack, key))
            report(GrammarError(f"{file}: inheritance cycle ({circle})"))
            return
        for parent in parents:
            if parent != key and parent in pending:
                visit(parent, (*stack, key))
        if key in failed:
            return
        broken = next(
            (
                parent
                for parent in parents
                if parent in failed or (parent in unreadable and parent not in found)
            ),
            None,
        )
        if broken is not None:
            failed.add(key)
            report(GrammarError(f"{file}: parent {broken!r} failed to load"))
            return
        try:
            load(file)
        except GrammarError as err:
            failed.add(key)
            report(err)

    for file in unordered:
        try:
            load(file)
        except GrammarError as err:
            # A child may name the file; it must not hide a later pack.
            unreadable.add(file.stem)
            report(err)
    for key in list(pending):
        visit(key, ())
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


def _load_builtins() -> tuple[dict[str, Scenario], dict[str, Scenario]]:
    base = base_grammar()
    toolchains: dict[str, Scenario] = {}
    for name in _BUILTIN_TOOLCHAINS:
        text = _read_resource("toolchains", f"{name}.toml")
        toolchains[name] = _parse_scenario(text, f"toolchains/{name}.toml", base, {})
    scenarios: dict[str, Scenario] = {}
    for name in _BUILTIN_PACKS:
        text = _read_resource(f"{name}.toml")
        scenario = _parse_scenario(
            text, f"{name}.toml", base, toolchains, is_trusted=True
        )
        scenarios[scenario.key] = scenario
    return toolchains, scenarios


TOOLCHAINS, SCENARIOS = _load_builtins()
