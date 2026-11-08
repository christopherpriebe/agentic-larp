"""The 0.1 public API. Changing any of these sets is a deliberate API change."""

import importlib
import inspect

import pytest

import agentic_larp

API = {
    "agentic_larp": {"main", "LarpError", "GrammarError", "__version__"},
    "agentic_larp.cli": {"main", "build_parser", "fit_agents"},
    "agentic_larp.sim": {
        "Sim",
        "SwarmSettings",
        "Agent",
        "Todo",
        "RunMode",
        "LogLine",
        "format_duration",
        "format_tokens",
        "Intern",
    },
    "agentic_larp.events": {
        "Event",
        "AgentSpawned",
        "LineShown",
        "TodoDone",
        "ScopeCreep",
        "AgentFinished",
        "Converged",
        "ShipStarted",
        "Report",
        "QuestionAsked",
        "QuestionAnswered",
        "EventBus",
    },
    "agentic_larp.stages": {
        "Session",
        "Stage",
        "ScreenStage",
        "FLOW",
        "END",
        "PlanStage",
        "WorkStage",
        "WrapStage",
        "ReadyStage",
        "ShipStage",
        "LaunchStage",
        "ReceiptStage",
        "AbandonStage",
        "run_flow",
        "run_screen",
        "stage_registry",
        "STAGE_ENTRY_POINT_GROUP",
        "Mode",
    },
    "agentic_larp.widgets": {
        "Wall",
        "Widget",
        "PanelWidget",
        "REGIONS",
        "HeaderWidget",
        "SwarmWidget",
        "FooterWidget",
        "AgentPanel",
        "QuestionWidget",
        "widget_registry",
        "render_entry",
        "SPOTLIGHT_HOLD",
        "Grid",
        "WIDGET_ENTRY_POINT_GROUP",
    },
    "agentic_larp.packs": {
        "Scenario",
        "Grammar",
        "SCENARIOS",
        "TOOLCHAINS",
        "load_scenario",
        "discover_scenarios",
        "default_pack_dirs",
        "pick_scenario",
        "generic_scenario",
        "task_words",
        "base_grammar",
        "parse_activity",
        "REQUIRED_SYMBOLS",
        "BOUND_SYMBOLS",
    },
    "agentic_larp.policies": {
        "ChoicePolicy",
        "RandomPolicy",
        "VariedPolicy",
        "PhasedPolicy",
        "PHASES",
        "policy_registry",
        "POLICY_ENTRY_POINT_GROUP",
    },
    "agentic_larp.apps": {
        "App",
        "AppContext",
        "Screen",
        "run_loop",
        "app_registry",
        "discover_apps",
        "APP_ENTRY_POINT_GROUP",
    },
    "agentic_larp.keys": {"Keys", "KeySource", "parse_keys", "is_interactive"},
    "agentic_larp.meltdown": {
        "ENDING_FLAG",
        "MELTDOWN_ENDING",
        "SUCCESS_ENDING",
        "DeathScreen",
        "EXIT_137",
        "KERNEL_PANIC",
        "BLUE_SCREEN",
        "DEATHS",
        "SHARED_ERRORS",
        "Meltdown",
        "MeltdownScreen",
        "run_meltdown",
        "is_doomed",
        "check_ending",
        "BreakableScreen",
        "play",
        "decay",
        "capture_frame",
    },
    "agentic_larp.plugins": {"load_registry"},
    "agentic_larp.questions": {"Option", "Question"},
}


@pytest.mark.parametrize("module", sorted(API))
def test_each_public_module_exports_exactly_its_api(module: str) -> None:
    imported = importlib.import_module(module)
    assert set(imported.__all__) == API[module]


@pytest.mark.parametrize("module", sorted(API))
def test_every_exported_name_resolves_and_is_documented(module: str) -> None:
    imported = importlib.import_module(module)
    assert (imported.__doc__ or "").strip(), module
    for name in imported.__all__:
        value = getattr(imported, name)
        if inspect.isclass(value) or inspect.isfunction(value):
            assert (value.__doc__ or "").strip(), f"{module}.{name}"


def test_the_root_no_longer_exports_internals() -> None:
    for name in ("Sim", "Keys", "parse_activity", "Theater", "DESCRIPTIONS", "Wall"):
        assert not hasattr(agentic_larp, name), name
    assert agentic_larp.__version__
