"""Cosplay as a 10x AI engineer: a terminal UI where a swarm of fake agents builds your app, then ships it."""

from importlib.metadata import version

from agentic_larp._cli import build_parser, fit_agents, main
from agentic_larp._keys import Keys, KeySource, is_interactive, parse_keys
from agentic_larp._scenarios import (
    SCENARIOS,
    Scenario,
    generic_scenario,
    pick_scenario,
    task_words,
)
from agentic_larp._sim import (
    Agent,
    Intern,
    LogLine,
    Sim,
    SwarmSettings,
    format_duration,
    format_tokens,
)
from agentic_larp._theater import ShowSettings, Theater, render_entry

__all__ = [
    "SCENARIOS",
    "Agent",
    "Intern",
    "KeySource",
    "Keys",
    "LogLine",
    "Scenario",
    "ShowSettings",
    "Sim",
    "SwarmSettings",
    "Theater",
    "__version__",
    "build_parser",
    "fit_agents",
    "format_duration",
    "format_tokens",
    "generic_scenario",
    "is_interactive",
    "main",
    "parse_keys",
    "pick_scenario",
    "render_entry",
    "task_words",
]

__version__ = version("agentic-larp")
