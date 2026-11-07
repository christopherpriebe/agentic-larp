"""The ``larp`` command."""

import argparse
import random
import subprocess
from importlib.metadata import version

from rich.console import Console

from agentic_larp._keys import is_interactive
from agentic_larp._scenarios import SCENARIOS, pick_scenario
from agentic_larp._sim import Sim, SwarmSettings
from agentic_larp._theater import (
    PANEL_MIN_HEIGHT,
    PANEL_MIN_WIDTH,
    ShowSettings,
    Theater,
)
from agentic_larp.apps import DESCRIPTIONS, App, AppContext, app_registry

_NON_INTERACTIVE_AUTO = 6.0
_BASE_TIMESCALE = 22.0
_MAX_AGENTS = 12
_CHROME_ROWS = 6
_SWARM_ROWS = 5
_INTERRUPTED = 130
_UNKNOWN_APP = 2


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
        choices=[*sorted(SCENARIOS), "generic"],
        help="force a scenario pack",
    )
    parser.add_argument(
        "-n",
        "--agents",
        type=int,
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
        "--auto",
        type=float,
        metavar="SECS",
        help="ship automatically after SECS (demo mode)",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="how fast everything happens (default 1.0)",
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
    args = build_parser().parse_args(argv)
    console = Console()
    apps = app_registry()
    if args.list:
        _print_list(console, apps)
        return 0
    auto = args.auto
    if auto is None and not is_interactive():
        auto = _NON_INTERACTIVE_AUTO
    try:
        if args.play:
            task = " ".join(args.task) or "the thing"
            return _launch(
                args.play, apps, AppContext(console=console, task=task, auto=auto)
            )
        return _run_show(args, console, apps, auto)
    except KeyboardInterrupt:
        console.print("\n[dim]ctrl-c. the agents will remember this.[/]")
        return _INTERRUPTED


def _run_show(
    args: argparse.Namespace,
    console: Console,
    apps: dict[str, App],
    auto: float | None,
) -> int:
    rng = random.Random(args.seed)
    scenario = pick_scenario(" ".join(args.task) or None, args.scenario, rng)
    interns = max(0, args.interns)
    width, height = console.size
    settings = SwarmSettings(
        agents=args.agents or fit_agents(width, height, has_interns=interns > 0),
        interns=interns,
        timescale=_BASE_TIMESCALE * args.speed,
        lead_model=args.lead_model,
        intern_model=args.intern_model,
    )
    sim = Sim(scenario, settings, rng)
    app = (args.app or scenario.app).lower()
    label = args.then.split()[0] if args.then else app.replace("none", "")
    show = ShowSettings(launch_label=label, auto=auto, pace=args.speed)
    if not Theater(sim, console, show).run():
        console.print(
            f"[dim]{len(sim.agents)} agents dismissed. nothing was built. as always.[/]"
        )
        return 0
    console.print(
        f"[bold green]✓ shipped[/] [bold]{scenario.task}[/] [dim]· {len(sim.agents)} agents · "
        f"{sim.total_calls:,} tool calls · ${sim.cost:,.2f} of imaginary compute[/]",
    )
    if args.then:
        return subprocess.call(args.then, shell=True)  # noqa: S602 - the user's own command; running it is the feature
    if app == "none":
        return 0
    return _launch(
        app, apps, AppContext(console=console, task=scenario.task, auto=auto)
    )


def _print_list(console: Console, apps: dict[str, App]) -> None:
    console.print("[bold]scenarios[/]  (picked by keywords in your task, or -s)")
    for key, scenario in SCENARIOS.items():
        console.print(
            f"  [cyan]{key:<11}[/] {scenario.task}  [dim]→ launches {scenario.app}[/]"
        )
    console.print("  [cyan]generic    [/] anything else you type")
    console.print("\n[bold]apps[/]  (--app NAME or --play NAME)")
    for name in apps:
        console.print(f"  [cyan]{name:<11}[/] {DESCRIPTIONS.get(name, 'plugin')}")


def _launch(name: str, apps: dict[str, App], context: AppContext) -> int:
    if name not in apps:
        context.console.print(f"[red]no app called {name!r}.[/] try: {', '.join(apps)}")
        return _UNKNOWN_APP
    apps[name](context)
    return 0
