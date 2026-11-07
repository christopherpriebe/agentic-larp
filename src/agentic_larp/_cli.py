"""The ``larp`` command."""

import argparse
import math
import random
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from typing import cast

from rich.console import Console
from rich.markup import escape

from agentic_larp._draw import PANEL_MIN_HEIGHT
from agentic_larp._errors import GrammarError, LarpError
from agentic_larp._flow import FLOW, Session, Stage, run_flow, stage_registry
from agentic_larp._grid import Grid
from agentic_larp._keys import is_interactive
from agentic_larp._packs import (
    SCENARIOS,
    TOOLCHAINS,
    Scenario,
    default_pack_dirs,
    discover_scenarios,
    load_scenario,
)
from agentic_larp._policies import ChoicePolicy, policy_registry
from agentic_larp._scenarios import pick_scenario
from agentic_larp._sim import RunMode, Sim, SwarmSettings
from agentic_larp._stages import LaunchStage, describe_unknown_app
from agentic_larp._wall import PANEL_MIN_WIDTH, Wall
from agentic_larp._widgets import PanelWidget, Widget, widget_registry
from agentic_larp.apps import App, app_registry
from agentic_larp.meltdown import check_ending

_NON_INTERACTIVE_AUTO = 6.0
_MAX_AGENTS = 12
_CHROME_ROWS = 6
_SWARM_ROWS = 5
_INTERRUPTED = 130
_BAD_PACK = 2
_BAD_FLAG = 2
_UNKNOWN_APP = 2


def _parse_speed(text: str) -> float:
    try:
        value = float(text)
    except ValueError:
        value = math.nan
    if not math.isfinite(value) or value <= 0:
        message = f"must be a finite number above 0, not {text!r}"
        raise argparse.ArgumentTypeError(message)
    return value


def _parse_length(text: str) -> float:
    return _parse_speed(text)


def _parse_agent_count(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        value = 0
    if value < 1:
        message = f"must be a whole number of at least 1, not {text!r}"
        raise argparse.ArgumentTypeError(message)
    return value


def _plugin_warner(console: Console) -> Callable[[str, Exception], None]:
    def warn(name: str, error: Exception) -> None:
        _print_unwrapped(console, f"[yellow]warning: {escape(f'{name}: {error}')}[/]")

    return warn


@dataclass(frozen=True, slots=True)
class _Plugins:
    apps: Mapping[str, App]
    stages: Mapping[str, Callable[[], Stage]]
    widgets: Mapping[str, Callable[[Wall], Widget | PanelWidget]]
    warn: Callable[[str, Exception], None]


def _check_policy(
    parser: argparse.ArgumentParser,
    registry: Mapping[str, Callable[[], ChoicePolicy]],
    name: str,
) -> Callable[[], ChoicePolicy]:
    factory = registry.get(name)
    if factory is None:
        parser.error(
            f"argument --policy: unknown policy {name!r}; try: {', '.join(registry)}"
        )
    if not callable(factory) or not callable(getattr(factory(), "choose", None)):
        parser.error(f"argument --policy: {name!r} is not a choice policy")
    return factory


def _parse_grid(text: str) -> Grid:
    try:
        return Grid.parse(text)
    except LarpError as err:
        raise argparse.ArgumentTypeError(str(err)) from err


def _parse_flag(text: str) -> tuple[str, str]:
    key, separator, value = text.partition("=")
    key, value = key.strip(), value.strip()
    if not separator or not key:
        message = f"expected KEY=VALUE, not {text!r}"
        raise argparse.ArgumentTypeError(message)
    return key, value


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for ``larp``.

    Returns:
        The parser.
    """
    parser = argparse.ArgumentParser(
        prog="larp",
        description="Pretend a swarm of AI agents is building your app. Type 'ship it'. Twice.",
        epilog=(
            'examples:  larp "build me a girlfriend"   larp -s hacker   '
            'larp --play stonks   larp --then "cmatrix"'
        ),
    )
    parser.add_argument(
        "task",
        nargs="*",
        help="what the agents are 'building' (default: a random scenario)",
    )
    parser.add_argument(
        "-s",
        "--scenario",
        action="append",
        metavar="PACK",
        help="force a scenario pack; repeat to mix packs across agents",
    )
    parser.add_argument(
        "--pack",
        action="append",
        type=Path,
        metavar="FILE",
        help="load a pack file (repeatable); see the README",
    )
    parser.add_argument(
        "--grid",
        type=_parse_grid,
        metavar="COLSxROWS",
        help="show a fixed grid of feeds and rotate a spotlight through the agents",
    )
    parser.add_argument(
        "-n",
        "--agents",
        type=_parse_agent_count,
        help="number of lead agents (default: fits your terminal)",
    )
    parser.add_argument(
        "-i",
        "--interns",
        type=int,
        default=16,
        help="number of tiny swarm agents (default 16; 0 hides them)",
    )
    parser.add_argument(
        "-a", "--app", help="app to launch after shipping (see --list), or 'none'"
    )
    parser.add_argument(
        "--then",
        metavar="CMD",
        help="shell command to run after shipping (your real app, cmatrix, ...)",
    )
    parser.add_argument(
        "--play", metavar="APP", help="skip the agents and launch an app"
    )
    parser.add_argument(
        "--policy",
        default="random",
        metavar="NAME",
        help="how repeated lines are chosen (see --list; default random)",
    )
    parser.add_argument(
        "--flag",
        action="append",
        dest="flags",
        default=[],
        type=_parse_flag,
        metavar="KEY=VALUE",
        help=(
            "set a session flag (repeatable; a repeated key keeps its last value); "
            "--flag ending=meltdown melts the app down"
        ),
    )
    parser.add_argument(
        "--auto",
        type=float,
        metavar="SECS",
        help="ship automatically after SECS (demo mode)",
    )
    parser.add_argument(
        "--speed",
        type=_parse_speed,
        default=1.0,
        help=(
            "how fast the agents work (default 1.0); the clock, --auto and "
            "every other timing are real seconds"
        ),
    )
    parser.add_argument(
        "--length",
        type=_parse_length,
        default=20.0,
        metavar="SECS",
        help="seconds the swarm takes to converge at speed 1 (default 20)",
    )
    parser.add_argument(
        "--forever",
        action="store_true",
        help="never converge: the agents keep finding more to do",
    )
    parser.add_argument("--lead-model", default="maestro", help="name for lead agents")
    parser.add_argument(
        "--intern-model", default="intern", help="name for swarm agents"
    )
    parser.add_argument(
        "--seed", type=int, help="random seed, for reproducible nonsense"
    )
    parser.add_argument("--list", action="store_true", help="list scenarios and apps")
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"agentic-larp {version('agentic-larp')}",
    )
    return parser


def fit_agents(width: int, height: int, *, has_interns: bool) -> int:
    """Choose how many lead agents fill a terminal without cramping.

    Args:
        width: Terminal columns.
        height: Terminal rows.
        has_interns: Whether the intern strip takes up rows.

    Returns:
        Between 2 and 12 agents.
    """
    columns = max(1, width // PANEL_MIN_WIDTH)
    usable = height - _CHROME_ROWS - (_SWARM_ROWS if has_interns else 0)
    rows = max(1, usable // (PANEL_MIN_HEIGHT + 2))
    return max(2, min(_MAX_AGENTS, columns * rows))


def main(argv: list[str] | None = None) -> int:
    """Run ``larp``.

    Args:
        argv: Arguments, without the program name; defaults to ``sys.argv[1:]``.

    Returns:
        The process exit code.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    console = Console()
    try:
        check_ending(dict(args.flags))
    except LarpError as err:
        _print_unwrapped(console, f"[red]{escape(str(err))}[/]")
        return _BAD_FLAG
    warn = _plugin_warner(console)
    apps = app_registry(on_error=warn)
    stages = stage_registry(on_error=warn)
    widgets = widget_registry(on_error=warn)
    try:
        packs = _collect_packs(args.pack or [], console)
    except LarpError as err:
        _print_unwrapped(console, f"[red]{escape(str(err))}[/]")
        return _BAD_PACK
    registry = policy_registry(on_error=warn)
    if args.list:
        _print_list(console, apps, packs, registry)
        return 0
    args.policy_factory = _check_policy(parser, registry, args.policy)
    auto = args.auto
    if auto is None and not is_interactive():
        auto = _NON_INTERACTIVE_AUTO
    try:
        if args.play:
            return _run_play(args, console, apps, auto)
        return _run_show(
            args,
            console,
            auto,
            packs,
            _Plugins(apps, stages, widgets, warn),
        )
    except KeyboardInterrupt:
        console.print("\n[dim]ctrl-c. the agents will remember this.[/]")
        return _INTERRUPTED


def _run_play(
    args: argparse.Namespace,
    console: Console,
    apps: Mapping[str, App],
    auto: float | None,
) -> int:
    if args.play not in apps:
        console.print(describe_unknown_app(args.play, apps))
        return _UNKNOWN_APP
    session = Session(
        console=console,
        task=" ".join(args.task) or "the thing",
        sim=None,
        rng=random.Random(args.seed),
        app=args.play,
        auto=auto,
        flags=dict(args.flags),
        apps=apps,
    )
    return run_flow(session, ("launch",), {"launch": LaunchStage})


def _run_show(
    args: argparse.Namespace,
    console: Console,
    auto: float | None,
    packs: Mapping[str, Scenario],
    plugins: _Plugins,
) -> int:
    rng = random.Random(args.seed)
    given_task = " ".join(args.task) or None
    try:
        if args.scenario:
            scenarios = [
                pick_scenario(given_task, key, rng, scenarios=packs)
                for key in args.scenario
            ]
        else:
            scenarios = [pick_scenario(given_task, None, rng, scenarios=packs)]
    except LarpError as err:
        _print_unwrapped(console, f"[red]{escape(str(err))}[/]")
        return _BAD_PACK
    interns = max(0, args.interns)
    width, height = console.size
    grid = cast("Grid | None", args.grid)
    if args.agents:
        agent_count = args.agents
    elif grid:
        agent_count = grid.cells
    else:
        agent_count = fit_agents(width, height, has_interns=interns > 0)
    settings = SwarmSettings(
        agents=agent_count,
        interns=interns,
        activity=args.speed,
        lead_model=args.lead_model,
        intern_model=args.intern_model,
        policy=args.policy_factory,
        mode=RunMode.ENDLESS if args.forever else RunMode.CONVERGE,
        length=args.length,
    )
    try:
        sim = Sim(scenarios, settings, rng)
        session = Session(
            console=console,
            task=sim.task,
            sim=sim,
            rng=rng,
            app=(args.app or sim.scenarios[0].app).lower(),
            then=args.then,
            auto=auto,
            grid=grid,
            flags=dict(args.flags),
            apps=plugins.apps,
            widgets=plugins.widgets,
            on_error=plugins.warn,
        )
        return run_flow(session, FLOW, plugins.stages)
    except LarpError as err:
        _print_unwrapped(console, f"[red]{escape(str(err))}[/]")
        return _BAD_PACK


def _print_unwrapped(console: Console, markup: str) -> None:
    console.print(markup, soft_wrap=True)


def _collect_packs(files: list[Path], console: Console) -> dict[str, Scenario]:
    def warn(error: GrammarError) -> None:
        _print_unwrapped(console, f"[yellow]warning: {escape(str(error))}[/]")

    packs = {**TOOLCHAINS, **SCENARIOS}
    packs.update(discover_scenarios(default_pack_dirs(), on_error=warn))
    for file in files:
        scenario = load_scenario(file, packs=packs)
        packs[scenario.key] = scenario
    return packs


def _print_list(
    console: Console,
    apps: dict[str, App],
    packs: Mapping[str, Scenario],
    policies: Mapping[str, Callable[[], ChoicePolicy]],
) -> None:
    console.print("[bold]scenarios[/]  (picked by keywords in your task, or -s)")
    for key, scenario in packs.items():
        if scenario.abstract:
            continue
        console.print(
            f"  [cyan]{escape(key):<11}[/] {escape(scenario.task)}  "
            f"[dim]→ launches {escape(scenario.app)}[/]"
        )
    console.print("  [cyan]generic    [/] anything else you type")
    console.print("\n[bold]toolchains[/]  (abstract; extend them from a pack)")
    for key, scenario in packs.items():
        if scenario.abstract:
            console.print(f"  [cyan]{escape(key):<11}[/]")
    console.print("\n[bold]policies[/]  (--policy NAME)")
    for name in policies:
        console.print(f"  [cyan]{escape(name):<11}[/]")
    console.print("\n[bold]apps[/]  (--app NAME or --play NAME)")
    for name, app in apps.items():
        console.print(f"  [cyan]{name:<11}[/] {escape(app.description)}")
