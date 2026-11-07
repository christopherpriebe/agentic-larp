"""Cosplay as a 10x AI engineer: a terminal UI where a swarm of fake agents builds your app, then ships it."""

from importlib.metadata import version

from agentic_larp._cli import build_parser, fit_agents, main
from agentic_larp._errors import GrammarError, LarpError
from agentic_larp._flow import (
    END,
    FLOW,
    STAGE_ENTRY_POINT_GROUP,
    ScreenStage,
    Session,
    Stage,
    run_flow,
    run_screen,
    stage_registry,
)
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
    TOOLCHAINS,
    Scenario,
    base_grammar,
    default_pack_dirs,
    discover_scenarios,
    load_scenario,
)
from agentic_larp._policies import (
    PHASES,
    POLICY_ENTRY_POINT_GROUP,
    ChoicePolicy,
    PhasedPolicy,
    RandomPolicy,
    VariedPolicy,
    policy_registry,
)
from agentic_larp._scenarios import generic_scenario, pick_scenario, task_words
from agentic_larp._sim import (
    Agent,
    Intern,
    RunMode,
    Sim,
    SwarmSettings,
    Todo,
    format_duration,
    format_tokens,
)
from agentic_larp._stages import (
    AbandonStage,
    LaunchStage,
    PlanStage,
    ReadyStage,
    ReceiptStage,
    ShipStage,
    WorkStage,
    WrapStage,
)
from agentic_larp._wall import SPOTLIGHT_HOLD, Wall, render_entry

__all__ = [
    "BOUND_SYMBOLS",
    "END",
    "FLOW",
    "PHASES",
    "POLICY_ENTRY_POINT_GROUP",
    "REQUIRED_SYMBOLS",
    "SCENARIOS",
    "SPOTLIGHT_HOLD",
    "STAGE_ENTRY_POINT_GROUP",
    "TOOLCHAINS",
    "AbandonStage",
    "Agent",
    "ChoicePolicy",
    "Grammar",
    "GrammarError",
    "Grid",
    "Intern",
    "KeySource",
    "Keys",
    "LarpError",
    "LaunchStage",
    "LogLine",
    "PhasedPolicy",
    "PlanStage",
    "RandomPolicy",
    "ReadyStage",
    "ReceiptStage",
    "RunMode",
    "Scenario",
    "ScreenStage",
    "Session",
    "ShipStage",
    "Sim",
    "Stage",
    "SwarmSettings",
    "Todo",
    "VariedPolicy",
    "Wall",
    "WorkStage",
    "WrapStage",
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
    "policy_registry",
    "render_entry",
    "run_flow",
    "run_screen",
    "stage_registry",
    "task_words",
]

__version__ = version("agentic-larp")
