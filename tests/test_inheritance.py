import random
from collections import deque
from pathlib import Path

import pytest

from agentic_larp import GrammarError, LarpError, main
from agentic_larp.packs import (
    SCENARIOS,
    TOOLCHAINS,
    discover_scenarios,
    load_scenario,
    pick_scenario,
)
from agentic_larp.sim import LogLine, RunMode, Sim, SwarmSettings


def write(directory: Path, name: str, text: str) -> Path:
    path = directory / f"{name}.toml"
    path.write_text(text, encoding="utf-8")
    return path


PARENT = """
[pack]
key = "parent"
task = "parent task"
abstract = true

[rules]
word = ["alpha", "beta"]
command = ["make parent"]
"""


def test_toolchains_ship_and_are_abstract() -> None:
    assert {"cpp", "typescript", "python", "rust"} <= set(TOOLCHAINS)
    assert all(pack.abstract for pack in TOOLCHAINS.values())
    assert not any(pack.abstract for pack in SCENARIOS.values())
    assert not set(TOOLCHAINS) & set(SCENARIOS)


@pytest.mark.parametrize(
    ("key", "parent"),
    [
        ("girlfriend", "cpp"),
        ("prod", "rust"),
        ("startup", "typescript"),
        ("wrapper", "python"),
    ],
)
def test_builtin_packs_inherit_a_toolchain(key: str, parent: str) -> None:
    assert parent in SCENARIOS[key].parents


def test_child_rules_replace_and_extend_appends(tmp_path: Path) -> None:
    parent = load_scenario(write(tmp_path, "parent", PARENT))
    child = load_scenario(
        write(
            tmp_path,
            "child",
            """
[pack]
key = "child"
task = "child task"
extends = ["parent"]

[areas]
x = ["x.py"]

[rules]
command = ["make child"]

[extend]
word = ["gamma"]
quip = ["extra quip"]
""",
        ),
        packs={"parent": parent},
    )
    rules = child.grammar.rules
    assert [text for text, _ in rules["word"]] == ["alpha", "beta", "gamma"]
    assert [text for text, _ in rules["command"]] == ["make child"]
    assert ("extra quip", 1.0) in rules["quip"]
    assert len(rules["quip"]) > 1  # the base quips are kept, the extra one appended
    assert child.parents == ("parent",)


def test_extend_after_replace_in_the_same_pack(tmp_path: Path) -> None:
    parent = load_scenario(write(tmp_path, "parent", PARENT))
    child = load_scenario(
        write(
            tmp_path,
            "child",
            """
[pack]
key = "child"
task = "t"
extends = "parent"

[areas]
x = ["x.py"]

[rules]
word = ["zeta"]

[extend]
word = ["eta"]
""",
        ),
        packs={"parent": parent},
    )
    assert [text for text, _ in child.grammar.rules["word"]] == ["zeta", "eta"]


def test_later_parents_win_and_the_child_wins_over_all(tmp_path: Path) -> None:
    first = load_scenario(
        write(tmp_path, "first", PARENT.replace('"parent"', '"first"'))
    )
    second = load_scenario(
        write(
            tmp_path,
            "second",
            '[pack]\nkey = "second"\ntask = "t"\nabstract = true\n[rules]\nword = ["second"]\n',
        )
    )
    child = load_scenario(
        write(
            tmp_path,
            "child",
            '[pack]\nkey = "child"\ntask = "t"\nextends = ["first", "second"]\n[areas]\nx = ["x.py"]\n',
        ),
        packs={"first": first, "second": second},
    )
    assert [text for text, _ in child.grammar.rules["word"]] == ["second"]
    assert [text for text, _ in child.grammar.rules["command"]] == ["make parent"]


def test_a_child_inherits_areas_task_and_app_but_not_keywords(tmp_path: Path) -> None:
    child = load_scenario(
        write(
            tmp_path,
            "her_v2",
            '[pack]\nkey = "her_v2"\nextends = ["girlfriend"]\nkeywords = ["sequel"]\n[extend]\nquip = ["She got an update."]\n',
        )
    )
    girlfriend = SCENARIOS["girlfriend"]
    assert child.areas == girlfriend.areas
    assert child.app == girlfriend.app
    assert child.task == girlfriend.task
    assert child.keywords == ("sequel",)
    assert ("She got an update.", 1.0) in child.grammar.rules["quip"]


def test_user_packs_can_extend_builtin_toolchains(tmp_path: Path) -> None:
    pack = load_scenario(
        write(
            tmp_path,
            "game",
            '[pack]\nkey = "game"\ntask = "build a game engine"\nextends = ["cpp"]\n[areas]\nrender = ["render.cpp"]\n',
        )
    )
    assert pack.parents == ("cpp",)
    assert len(pack.grammar.rules["command"]) >= len(
        TOOLCHAINS["cpp"].grammar.rules["command"]
    )


def test_discover_resolves_extends_regardless_of_file_order(tmp_path: Path) -> None:
    write(
        tmp_path,
        "a_child",
        '[pack]\nkey = "a_child"\ntask = "t"\nextends = ["z_parent"]\n[areas]\nx = ["x.py"]\n',
    )
    write(tmp_path, "z_parent", PARENT.replace('"parent"', '"z_parent"'))
    found = discover_scenarios([tmp_path])
    assert found["a_child"].parents == ("z_parent",)
    assert [t for t, _ in found["a_child"].grammar.rules["word"]] == ["alpha", "beta"]


def test_discovered_abstract_packs_cannot_be_picked_to_run(
    tmp_path: Path,
) -> None:
    write(tmp_path, "z_parent", PARENT.replace('"parent"', '"z_parent"'))
    with pytest.raises(LarpError, match="abstract"):
        pick_scenario(None, "z_parent", scenarios=discover_scenarios([tmp_path]))


def test_unknown_parent_is_an_error_naming_the_file(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        "orphan",
        '[pack]\nkey = "orphan"\ntask = "t"\nextends = ["nope"]\n[areas]\nx = ["x.py"]\n',
    )
    with pytest.raises(GrammarError, match="unknown parent 'nope'") as caught:
        load_scenario(path)
    assert "orphan.toml" in str(caught.value)


def test_inheritance_cycles_are_an_error(tmp_path: Path) -> None:
    write(
        tmp_path,
        "a",
        '[pack]\nkey = "a"\ntask = "t"\nextends = ["b"]\n[areas]\nx = ["x.py"]\n',
    )
    write(
        tmp_path,
        "b",
        '[pack]\nkey = "b"\ntask = "t"\nextends = ["a"]\n[areas]\nx = ["x.py"]\n',
    )
    with pytest.raises(GrammarError, match="inheritance cycle"):
        discover_scenarios([tmp_path])


@pytest.mark.parametrize("key", ["cpp", "rust"])
def test_toolchains_cannot_be_run_directly(key: str) -> None:
    with pytest.raises(LarpError, match="abstract"):
        pick_scenario(None, key)


def test_cli_rejects_a_toolchain_scenario(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["-s", "cpp", "--auto", "1"]) == 2
    assert "abstract" in capsys.readouterr().out


def test_list_shows_toolchains(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--list"]) == 0
    text = capsys.readouterr().out
    assert "toolchains" in text
    assert "cpp" in text


def run_lines(key: str, seconds: float = 60.0) -> list[LogLine]:
    sim = Sim(
        [pick_scenario(None, key)],
        SwarmSettings(agents=8, interns=0, mode=RunMode.ENDLESS),
        random.Random(3),
    )
    for agent in sim.agents:
        agent.log = deque(agent.log)
    for _ in range(int(seconds / 0.05)):
        sim.tick(0.05)
    return [line for agent in sim.agents for line in agent.log]


def test_the_cpp_toolchain_makes_girlfriend_look_like_real_cpp() -> None:
    lines = run_lines("girlfriend")
    bash = {line.text for line in lines if line.kind == "tool" and line.label == "Bash"}
    everything = "\n".join(line.text for line in lines)
    assert len(bash) >= 60  # was 24 before toolchains
    assert "Building CXX object" in everything
    assert any(
        word in everything for word in ("ctest", "valgrind", "gdb", "clang-tidy")
    )


def test_girlfriend_keeps_its_own_flavor() -> None:
    lines = run_lines("girlfriend")
    texts = "\n".join(line.text for line in lines)
    quips = {line.text for line in lines if line.kind == "quip"}
    assert quips & {"She is gorgeous now.", "Ring sized.", "She remembers you."}
    assert any(name in texts for name in ("heart", "face", "ring"))


def test_a_config_pack_can_extend_the_builtin_it_replaces(tmp_path: Path) -> None:
    write(
        tmp_path,
        "girlfriend",
        '[pack]\nkey = "girlfriend"\nextends = "girlfriend"\n[extend]\nquip = ["She got a patch."]\n',
    )
    errors: list[GrammarError] = []
    found = discover_scenarios([tmp_path], on_error=errors.append)
    assert errors == []
    pack = found["girlfriend"]
    assert pack.parents == ("girlfriend",)
    assert pack.areas == SCENARIOS["girlfriend"].areas
    assert ("She got a patch.", 1.0) in pack.grammar.rules["quip"]


def test_a_child_of_a_broken_parent_says_the_parent_failed(tmp_path: Path) -> None:
    write(tmp_path, "z_broken", "[pack\nkey = 'z_broken'")
    write(
        tmp_path,
        "a_child",
        '[pack]\nkey = "a_child"\ntask = "t"\nextends = ["z_broken"]\n[areas]\nx = ["x.py"]\n',
    )
    errors: list[GrammarError] = []
    found = discover_scenarios([tmp_path], on_error=errors.append)
    assert "a_child" not in found
    messages = " | ".join(str(error) for error in errors)
    assert "parent 'z_broken' failed to load" in messages
    assert "unknown parent" not in messages


def test_picking_from_only_abstract_packs_is_a_clear_error(tmp_path: Path) -> None:
    packs = discover_scenarios(
        [write(tmp_path, "only", PARENT.replace('"parent"', '"only"'))]
    )
    with pytest.raises(LarpError, match="no runnable pack"):
        pick_scenario(None, scenarios=packs)


NUMBER_RULES = (
    "build_result",
    "configure_result",
    "ccache_result",
    "debug_result",
    "analysis_result",
    "test_result",
    "test_fail",
    "result",
    "compile_error",
    "anytime",
    "build",
    "test",
    "debug",
)


@pytest.mark.parametrize("key", ["cpp", "typescript", "python", "rust"])
def test_toolchain_numbers_are_not_all_the_same_placeholder(key: str) -> None:
    grammar = TOOLCHAINS[key].grammar
    bindings = {
        "file": "heart.cpp",
        "area": "heart",
        "agent": "maestro-1",
        "intern": "intern-01",
        "n": "777",
    }
    rng = random.Random(0)
    lines = [
        grammar.expand(rule, rng, bindings)
        for rule in NUMBER_RULES
        if rule in grammar.rules
        for _ in range(150)
    ]
    text = "\n".join(lines)
    assert "777%" not in text
    assert "777.0 %" not in text
    assert ":777:777" not in text
    assert "-j777" not in text
    assert "-777" not in text
    assert "777 files changed" not in text
