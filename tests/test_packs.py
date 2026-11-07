import random
from pathlib import Path

import pytest

from agentic_larp import (
    BOUND_SYMBOLS,
    REQUIRED_SYMBOLS,
    SCENARIOS,
    GrammarError,
    LarpError,
    Sim,
    SwarmSettings,
    base_grammar,
    default_pack_dirs,
    discover_scenarios,
    load_scenario,
    parse_activity,
    pick_scenario,
    render_entry,
)

MINIMAL = """
[pack]
key = "{key}"
task = "build {key}"
keywords = ["{key}"]
app = "stonks"

[areas]
alpha = ["alpha.py"]
beta = ["beta.py", "beta_test.py"]

[rules]
quip = ["{key} quip"]
final = ["{key} done"]
"""


def write_pack(directory: Path, key: str, body: str = MINIMAL) -> Path:
    path = directory / f"{key}.toml"
    path.write_text(body.format(key=key), encoding="utf-8")
    return path


def test_base_grammar_supplies_every_required_symbol() -> None:
    base_grammar().check(required=REQUIRED_SYMBOLS, bound=BOUND_SYMBOLS)


def test_load_scenario_reads_a_pack_over_the_base(tmp_path: Path) -> None:
    scenario = load_scenario(write_pack(tmp_path, "mini"))
    assert scenario.key == "mini"
    assert scenario.task == "build mini"
    assert scenario.keywords == ("mini",)
    assert scenario.app == "stonks"
    assert scenario.areas == {
        "alpha": ("alpha.py",),
        "beta": ("beta.py", "beta_test.py"),
    }
    assert scenario.grammar.expand("quip", random.Random(0)) == "mini quip"
    assert "action" in scenario.grammar.rules  # inherited from the base grammar


def test_load_scenario_defaults_keywords_and_app(tmp_path: Path) -> None:
    path = tmp_path / "bare.toml"
    path.write_text(
        '[pack]\nkey = "bare"\ntask = "t"\n[areas]\nx = ["x.py"]\n', encoding="utf-8"
    )
    scenario = load_scenario(path)
    assert scenario.keywords == ()
    assert scenario.app == "deploy"


def test_area_rules_override_only_that_area(tmp_path: Path) -> None:
    body = MINIMAL.replace(
        'beta = ["beta.py", "beta_test.py"]',
        '[areas.beta]\nfiles = ["beta.py"]\nrules = {{ quip = ["beta only"] }}',
    )
    # [areas.beta] must come after the plain [areas] keys, which it does.
    scenario = load_scenario(write_pack(tmp_path, "mixed", body))
    rng = random.Random(0)
    assert scenario.areas["beta"] == ("beta.py",)
    assert scenario.grammar_for("beta").expand("quip", rng) == "beta only"
    assert scenario.grammar_for("alpha").expand("quip", rng) == "mixed quip"


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("[pack]\ntask = 't'\n[areas]\nx = ['x.py']\n", "missing \\[pack\\] key"),
        ("[pack]\nkey = 'k'\n[areas]\nx = ['x.py']\n", "missing \\[pack\\] task"),
        ("[pack]\nkey = 'k'\ntask = 't'\n", "no \\[areas\\]"),
        ("[pack\nkey = 'k'", "not valid TOML"),
        (
            "[pack]\nkey='k'\ntask='t'\n[areas]\nx=['x.py']\n[rules]\naction='#nowhere#'\n",
            "undefined symbols: nowhere",
        ),
        (
            "[pack]\nkey='k'\ntask='t'\n[areas]\nx=['x.py']\n[rules]\nquip=[]\n",
            "'quip' has no alternatives",
        ),
    ],
)
def test_load_scenario_names_the_file_in_every_error(
    tmp_path: Path, body: str, message: str
) -> None:
    path = tmp_path / "broken.toml"
    path.write_text(body, encoding="utf-8")
    with pytest.raises(GrammarError, match=message) as caught:
        load_scenario(path)
    assert "broken.toml" in str(caught.value)


def test_discover_scenarios_reads_files_and_directories(tmp_path: Path) -> None:
    folder = tmp_path / "packs"
    folder.mkdir()
    write_pack(folder, "one")
    write_pack(folder, "two")
    (folder / "notes.txt").write_text("not a pack", encoding="utf-8")
    single = write_pack(tmp_path, "three")
    found = discover_scenarios([folder, single, tmp_path / "missing"])
    assert sorted(found) == ["one", "three", "two"]


def test_discover_scenarios_later_paths_win(tmp_path: Path) -> None:
    first, second = tmp_path / "a", tmp_path / "b"
    first.mkdir()
    second.mkdir()
    write_pack(first, "same")
    (second / "same.toml").write_text(
        MINIMAL.format(key="same").replace(
            'task = "build same"', 'task = "second wins"'
        ),
        encoding="utf-8",
    )
    assert discover_scenarios([first, second])["same"].task == "second wins"


def test_discover_scenarios_raises_by_default(tmp_path: Path) -> None:
    (tmp_path / "bad.toml").write_text("[pack", encoding="utf-8")
    with pytest.raises(GrammarError, match=r"bad\.toml"):
        discover_scenarios([tmp_path])


def test_discover_scenarios_can_skip_broken_files(tmp_path: Path) -> None:
    (tmp_path / "bad.toml").write_text("[pack", encoding="utf-8")
    write_pack(tmp_path, "good")
    errors: list[GrammarError] = []
    found = discover_scenarios([tmp_path], on_error=errors.append)
    assert list(found) == ["good"]
    assert len(errors) == 1
    assert "bad.toml" in str(errors[0])


def test_default_pack_dirs_follow_xdg(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert default_pack_dirs() == [tmp_path / "agentic-larp" / "packs"]


def test_default_pack_dirs_fall_back_to_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert default_pack_dirs() == [tmp_path / ".config" / "agentic-larp" / "packs"]


@pytest.mark.parametrize("key", sorted(SCENARIOS))
def test_builtin_packs_produce_drawable_activity(key: str) -> None:
    scenario = SCENARIOS[key]
    rng = random.Random(1)
    bindings = {
        "file": "x.py",
        "area": "x",
        "agent": "maestro-1",
        "intern": "intern-01",
        "n": "4",
    }
    for area in scenario.areas:
        grammar = scenario.grammar_for(area)
        grammar.check(required=REQUIRED_SYMBOLS, bound=BOUND_SYMBOLS)
        for _ in range(50):
            lines = parse_activity(grammar.expand("action", rng, bindings))
            assert lines
            for line in lines:
                assert render_entry(line, 40).cell_len == 40
        assert grammar.expand("quip", rng, bindings)
        assert grammar.expand("final", rng, bindings)
        assert grammar.expand("intern_task", rng, bindings)


def test_builtin_packs_keep_their_apps() -> None:
    assert {key: s.app for key, s in SCENARIOS.items()} == {
        "girlfriend": "call",
        "startup": "stonks",
        "hacker": "hacker",
        "prod": "deploy",
        "dropship": "dropship",
        "memecoin": "memecoin",
        "wrapper": "wrapper",
        "nft": "nft",
    }


def test_pick_scenario_finds_custom_packs(tmp_path: Path) -> None:
    custom = discover_scenarios([write_pack(tmp_path, "zebra")])
    available = {**SCENARIOS, **custom}
    assert pick_scenario(None, "zebra", scenarios=available).key == "zebra"
    assert pick_scenario("I want a zebra", scenarios=available).key == "zebra"


def test_pick_scenario_rejects_an_unknown_key() -> None:
    with pytest.raises(LarpError, match="no pack called 'nope'"):
        pick_scenario(None, "nope")


def test_sim_deals_agents_across_packs_in_turn(tmp_path: Path) -> None:
    first = load_scenario(write_pack(tmp_path, "first"))
    second = load_scenario(write_pack(tmp_path, "second"))
    sim = Sim([first, second], SwarmSettings(agents=4, interns=0), random.Random(0))
    assert [agent.scenario_key for agent in sim.agents] == [
        "first",
        "second",
        "first",
        "second",
    ]
    assert [agent.area for agent in sim.agents] == ["alpha", "alpha", "beta", "beta"]
    assert sim.task == "build first"


def test_sim_uses_area_rules_for_that_areas_agent(tmp_path: Path) -> None:
    body = MINIMAL.replace(
        'beta = ["beta.py", "beta_test.py"]',
        '[areas.beta]\nfiles = ["beta.py"]\nrules = {{ quip = ["BETA-ONLY"] }}',
    )
    scenario = load_scenario(write_pack(tmp_path, "solo", body))
    sim = Sim([scenario], SwarmSettings(agents=2, interns=0), random.Random(3))
    for _ in range(1200):
        sim.tick(0.05)
    quips = {
        agent.area: {line.text for line in agent.log if line.kind == "quip"}
        for agent in sim.agents
    }
    assert "BETA-ONLY" in quips["beta"]
    assert "BETA-ONLY" not in quips["alpha"]
    assert "solo quip" in quips["alpha"]


def test_sim_task_can_be_overridden(tmp_path: Path) -> None:
    scenario = load_scenario(write_pack(tmp_path, "t"))
    assert Sim([scenario], task="my own words").task == "my own words"


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (
            "[pack]\nkey='k'\ntask='t'\n[areas]\nx=[]\n",
            "area 'x' has no files",
        ),
        (
            "[pack]\nkey='k'\ntask='t'\n[areas]\nx=['x.py']\n[rules]\naction='Edit #file#'\n",
            "unknown tag",
        ),
        (
            "[pack]\nkey='k'\ntask='t'\n[areas]\nx=['x.py']\n[rules]\ncode=['#word.lower#']\n",
            "unknown modifier 'lower'",
        ),
        (
            "[pack]\nkey='k'\ntask='t'\napp=3\n[areas]\nx=['x.py']\n",
            "\\[pack\\] app must be text",
        ),
        (
            "[pack]\nkey='generic'\ntask='t'\n[areas]\nx=['x.py']\n",
            "'generic' is reserved",
        ),
        (
            (
                "[pack]\nkey='k'\ntask='t'\n[areas]\n"
                "[areas.x]\nfiles=['x.py']\nrules={ only_here = 'hi' }\n"
                "[rules]\nintern_task='#only_here#'\n"
            ),
            "undefined symbols: only_here",
        ),
    ],
)
def test_load_scenario_rejects_packs_that_would_fail_mid_show(
    tmp_path: Path, body: str, message: str
) -> None:
    path = tmp_path / "late.toml"
    path.write_text(body, encoding="utf-8")
    with pytest.raises(GrammarError, match=message) as caught:
        load_scenario(path)
    assert "late.toml" in str(caught.value)


def test_no_interns_means_no_delegation(tmp_path: Path) -> None:
    scenario = load_scenario(write_pack(tmp_path, "solo"))
    sim = Sim([scenario], SwarmSettings(agents=3, interns=0), random.Random(5))
    for _ in range(2000):
        sim.tick(0.05)
    tools = {
        line.label for agent in sim.agents for line in agent.log if line.kind == "tool"
    }
    assert "Task" not in tools
    assert {"Edit", "Bash"} <= tools


def test_keywords_match_whole_words_only(tmp_path: Path) -> None:
    ai = load_scenario(write_pack(tmp_path, "ai"))
    packs = {"ai": ai}
    assert pick_scenario("fix the mainframe", scenarios=packs).key == "generic"
    assert pick_scenario("build an AI wrapper", scenarios=packs).key == "ai"
    assert pick_scenario("ai-powered toaster", scenarios=packs).key == "ai"


def keyword_pack(tmp_path: Path, keyword: str) -> Path:
    path = tmp_path / "kw.toml"
    path.write_text(
        f'[pack]\nkey = "kw"\ntask = "t"\nkeywords = ["{keyword}"]\n[areas]\nx = ["x.py"]\n',
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize(
    ("keyword", "task", "expected"),
    [
        ("c++", "rewrite it in c++", "kw"),
        ("c++", "rewrite it in c", "generic"),
        ("node.js", "a node.js app", "kw"),
        ("node.js", "a nodexjs app", "generic"),
    ],
)
def test_keywords_with_regex_characters_match_literally(
    tmp_path: Path, keyword: str, task: str, expected: str
) -> None:
    packs = {"kw": load_scenario(keyword_pack(tmp_path, keyword))}
    assert pick_scenario(task, scenarios=packs).key == expected


def test_empty_keywords_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(GrammarError, match="empty keyword"):
        load_scenario(keyword_pack(tmp_path, " "))


@pytest.mark.parametrize(
    ("task", "key"),
    [
        ("hacking the gibson", "hacker"),
        ("shipping on a friday", "prod"),
        ("two startups walk into a bar", "startup"),
    ],
)
def test_builtin_keywords_cover_common_inflections(task: str, key: str) -> None:
    assert pick_scenario(task).key == key


@pytest.mark.parametrize(
    ("task", "key"),
    [
        ("start a dropshipping store", "dropship"),
        ("launch a memecoin", "memecoin"),
        ("build a gpt wrapper", "wrapper"),
        ("mint an nft collection", "nft"),
        ("deploy a single server", "prod"),
    ],
)
def test_the_pack_with_the_most_keyword_hits_wins(task: str, key: str) -> None:
    assert pick_scenario(task).key == key


def test_ties_go_to_the_earlier_pack(tmp_path: Path) -> None:
    first = load_scenario(keyword_pack(tmp_path, "alpha"))
    second_path = tmp_path / "other.toml"
    second_path.write_text(
        '[pack]\nkey = "other"\ntask = "t"\nkeywords = ["beta", "gamma"]\n[areas]\nx = ["x.py"]\n',
        encoding="utf-8",
    )
    second = load_scenario(second_path)
    packs = {"kw": first, "other": second}
    assert pick_scenario("alpha beta", scenarios=packs).key == "kw"
    # repeating a keyword doesn't count twice; matching more distinct keywords does
    assert pick_scenario("beta alpha beta", scenarios=packs).key == "kw"
    assert pick_scenario("alpha beta gamma", scenarios=packs).key == "other"


def test_keywords_are_stored_stripped(tmp_path: Path) -> None:
    scenario = load_scenario(keyword_pack(tmp_path, "  zebra "))
    assert scenario.keywords == ("zebra",)
    assert pick_scenario("a zebra app", scenarios={"kw": scenario}).key == "kw"


@pytest.mark.parametrize(
    "task",
    [
        "jwt token refresh",
        "key-value store",
        "garbage collection tuning",
        "user agent parser",
        "command prompt theme",
        "i'm bored, build something",
    ],
)
def test_everyday_programming_words_do_not_trigger_grift_packs(task: str) -> None:
    assert pick_scenario(task).key == "generic"
