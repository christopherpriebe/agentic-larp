"""Cosplay as a 10x AI engineer: a terminal UI where a swarm of fake agents builds your app, then ships it."""

from importlib.metadata import version

from agentic_larp._cli import build_parser, fit_agents, main
from agentic_larp._errors import GrammarError, LarpError
from agentic_larp._grammar import (
    BOUND_SYMBOLS,
    REQUIRED_SYMBOLS,
    Grammar,
    parse_activity,
)
from agentic_larp._grid import Grid
from agentic_larp._keys import Keys, KeySource, is_interactive, parse_keys
from agentic_larp._log import LogLine
from agentic_larp._packs import (
    SCENARIOS,
    Scenario,
    base_grammar,
    default_pack_dirs,
    discover_scenarios,
    load_scenario,
)
from agentic_larp._scenarios import generic_scenario, pick_scenario, task_words
from agentic_larp._sim import (
    Agent,
    Intern,
    Sim,
    SwarmSettings,
    format_duration,
    format_tokens,
)
from agentic_larp._theater import SPOTLIGHT_HOLD, ShowSettings, Theater, render_entry

__all__ = [
    "BOUND_SYMBOLS",
    "REQUIRED_SYMBOLS",
    "SCENARIOS",
    "SPOTLIGHT_HOLD",
    "Agent",
    "Grammar",
    "GrammarError",
    "Grid",
    "Intern",
    "KeySource",
    "Keys",
    "LarpError",
    "LogLine",
    "Scenario",
    "ShowSettings",
    "Sim",
    "SwarmSettings",
    "Theater",
    "__version__",
    "base_grammar",
    "build_parser",
    "default_pack_dirs",
    "discover_scenarios",
    "fit_agents",
    "format_duration",
    "format_tokens",
    "generic_scenario",
    "is_interactive",
    "load_scenario",
    "main",
    "parse_activity",
    "parse_keys",
    "pick_scenario",
    "render_entry",
    "task_words",
]

__version__ = version("agentic-larp")
