import itertools
import random
import re
from pathlib import Path
from typing import Literal

import pytest
from rich.console import Console

from agentic_larp.packs import as_transcript, load_scenario, pick_scenario
from agentic_larp.sim import LogLine, RunMode, Sim, SwarmSettings
from agentic_larp.widgets import AgentPanel, Wall, render_entry

COLLAPSED = re.compile(r"^… \+\d+ lines \(ctrl\+o to expand\)$")

QUIP_PACK = """
[pack]
key = "acronyms"
task = "make CI green"

[areas]
core = ["core.py"]

[rules]
quip = ["CI is green.", "I fixed it.", "A/B test passed."]
"""


def run_sim(
    settings: SwarmSettings, seconds: float, seed: int = 7
) -> tuple[Sim, list[list[tuple[str, LogLine]]]]:
    """Run a prod sim and record, per tick, the lines each agent gained."""
    sim = Sim([pick_scenario(None, "prod")], settings, random.Random(seed))
    seen = {agent.name: len(agent.log) for agent in sim.agents}
    ticks: list[list[tuple[str, LogLine]]] = []
    for _ in range(int(seconds / 0.05)):
        sim.tick(0.05)
        gained: list[tuple[str, LogLine]] = []
        for agent in sim.agents:
            log = list(agent.log)
            gained += [(agent.name, line) for line in log[seen.get(agent.name, 0) :]]
            seen[agent.name] = len(log)
        ticks.append(gained)
    return sim, ticks


def uncapped(agents: int = 4) -> SwarmSettings:
    return SwarmSettings(
        agents=agents, interns=0, mode=RunMode.ENDLESS, log_length=None, length=20.0
    )


# ---- as_transcript: the parsed activity reshaped like Claude Code ------------


def test_an_edit_leads_with_a_summary_that_counts_its_diff() -> None:
    lines = [
        LogLine("tool", "cache.rs", "Edit"),
        LogLine("diff", "fn cache() -> Shard {", "-", 183),
        LogLine("diff", "fn cache() -> Replicas {", "+", 184),
        LogLine("diff", "self.replicas.clone()", "+", 185),
        LogLine("result", "Added 1024 lines", "dim"),
    ]
    assert as_transcript(lines) == [
        LogLine("tool", "cache.rs", "Edit"),
        LogLine("result", "Updated cache.rs with 2 additions and 1 removal", "dim"),
        LogLine("diff", "fn cache() -> Shard {", "-", 183),
        LogLine("diff", "fn cache() -> Replicas {", "+", 183),
        LogLine("diff", "self.replicas.clone()", "+", 184),
    ]


def test_an_edit_summary_names_only_what_changed() -> None:
    added = as_transcript(
        [LogLine("tool", "a.py", "Edit"), LogLine("diff", "x = 1", "+", 9)]
    )
    removed = as_transcript(
        [
            LogLine("tool", "a.py", "Edit"),
            LogLine("diff", "x = 1", "-", 9),
            LogLine("diff", "y = 2", "-", 10),
        ]
    )
    assert added[1] == LogLine("result", "Updated a.py with 1 addition", "dim")
    assert removed[1] == LogLine("result", "Updated a.py with 2 removals", "dim")
    assert [line.number for line in removed[2:]] == [9, 10]


def test_a_write_previews_its_lines_as_plain_numbered_code() -> None:
    lines = [
        LogLine("tool", "schema.rs", "Write"),
        LogLine("result", "Wrote 16 lines", "dim"),
        LogLine("diff", "use std::sync::Arc;", "+", 120),
        LogLine("diff", "pub struct Schema;", "+", 121),
    ]
    assert as_transcript(lines) == [
        LogLine("tool", "schema.rs", "Write"),
        LogLine("result", "Wrote 16 lines to schema.rs", "dim"),
        LogLine("diff", "use std::sync::Arc;", " ", 1),
        LogLine("diff", "pub struct Schema;", " ", 2),
    ]


def test_a_failed_command_reports_its_exit_code_first() -> None:
    lines = [
        LogLine("tool", "pytest -x", "Bash"),
        LogLine("result", "✗ 2 failed", "red"),
        LogLine("result", "FAILED tests/test_db.py::test_pool", "dim"),
        LogLine("quip", "Retrying."),
    ]
    assert as_transcript(lines) == [
        LogLine("tool", "pytest -x", "Bash"),
        LogLine("result", "Error: Exit code 1", "red"),
        LogLine("result", "2 failed", "red"),
        LogLine("result", "FAILED tests/test_db.py::test_pool", "dim"),
        LogLine("quip", "Retrying."),
    ]


def test_a_rust_panic_exits_with_101() -> None:
    lines = [
        LogLine("tool", "cargo test", "Bash"),
        LogLine("result", "✗ thread 'main' panicked at src/db.rs:4:2:", "red"),
    ]
    assert as_transcript(lines)[1] == LogLine("result", "Error: Exit code 101", "red")


def test_a_compile_error_exits_with_101() -> None:
    lines = [
        LogLine("tool", "cargo build", "Bash"),
        LogLine("result", "✗ error[E0599]: no method named `pool`", "red"),
    ]
    assert as_transcript(lines)[1] == LogLine("result", "Error: Exit code 101", "red")


def test_every_failure_line_in_a_block_loses_its_cross() -> None:
    lines = [
        LogLine("tool", "pytest", "Bash"),
        LogLine("result", "✗ 2 failed", "red"),
        LogLine("result", "✗ 1 error", "red"),
    ]
    assert [line.text for line in as_transcript(lines)[1:]] == [
        "Error: Exit code 1",
        "2 failed",
        "1 error",
    ]


def test_a_failed_edit_keeps_its_error_and_claims_nothing() -> None:
    lines = [
        LogLine("tool", "x.py", "Edit"),
        LogLine("diff", "y = 1", "+", 3),
        LogLine("result", "✗ conflict", "red"),
    ]
    assert as_transcript(lines) == [
        LogLine("tool", "x.py", "Edit"),
        LogLine("result", "Error: conflict", "red"),
    ]


def test_an_edit_counts_context_lines_on_both_sides() -> None:
    lines = [
        LogLine("tool", "a.py", "Edit"),
        LogLine("diff", "def f():", " ", 10),
        LogLine("diff", "    return 1", "-", 11),
        LogLine("diff", "    return 2", "+", 12),
        LogLine("diff", "", " ", 13),
        LogLine("diff", "x = f()", "+", 14),
    ]
    assert [(line.label, line.number) for line in as_transcript(lines)[2:]] == [
        (" ", 10),
        ("-", 11),
        ("+", 11),
        (" ", 12),
        ("+", 13),
    ]


def test_as_transcript_of_a_transcript_changes_nothing() -> None:
    raw = [
        LogLine("tool", "schema.rs", "Write"),
        LogLine("result", "Wrote 16 lines", "dim"),
        LogLine("diff", "pub struct Schema;", "+", 121),
        LogLine("tool", "cache.rs", "Edit"),
        LogLine("diff", "fn a() {}", "-", 7),
        LogLine("diff", "fn b() {}", "+", 8),
        LogLine("tool", "cargo test", "Bash"),
        LogLine("result", "✗ thread 'main' panicked at src/a.rs:1:1:", "red"),
    ]
    once = as_transcript(raw)
    assert as_transcript(once) == once


def test_a_failed_non_shell_tool_is_a_one_line_error() -> None:
    lines = [LogLine("tool", "db.rs", "Read"), LogLine("result", "✗ not found", "red")]
    assert as_transcript(lines) == [
        LogLine("tool", "db.rs", "Read"),
        LogLine("result", "Error: not found", "red"),
    ]


def test_ordinary_blocks_pass_through_unchanged() -> None:
    lines = [
        LogLine("tool", "db.rs", "Read"),
        LogLine("result", "Read 128 lines", "dim"),
        LogLine("quip", "p99 down to 4ms."),
        LogLine("tool", "cargo test", "Bash"),
        LogLine("result", "exit 0", "green"),
    ]
    assert as_transcript(lines) == lines


def random_lines(rng: random.Random) -> list[LogLine]:
    kinds: list[Literal["tool", "diff", "result", "quip"]] = [
        "tool",
        "diff",
        "result",
        "quip",
    ]
    labels = ["Edit", "Write", "Bash", "Read", "+", "-", " ", "red", "dim"]
    texts = ["x", "✗ boom", "Wrote 3 lines", "Added 2 lines", "panicked", "a b"]
    return [
        LogLine(
            rng.choice(kinds),
            rng.choice(texts),
            rng.choice(labels),
            rng.randint(1, 400),
        )
        for _ in range(rng.randint(0, 20))
    ]


@pytest.mark.parametrize("seed", range(200))
def test_as_transcript_keeps_every_turn_in_order(seed: int) -> None:
    def turns(seq: list[LogLine]) -> list[LogLine]:
        return [line for line in seq if line.kind in {"tool", "quip"}]

    lines = random_lines(random.Random(seed))
    assert turns(as_transcript(lines)) == turns(lines)


# ---- the sim streams Claude Code-shaped turns --------------------------------


def test_an_edit_and_its_diff_land_together() -> None:
    _, ticks = run_sim(uncapped(), 40)
    summaries = 0
    for gained in ticks:
        for index, (name, line) in enumerate(gained):
            if line.kind == "result" and line.text.startswith("Updated "):
                summaries += 1
                rest = gained[index + 1 :]
                assert rest
                assert rest[0][0] == name
                assert rest[0][1].kind == "diff"
    assert summaries > 0


def test_a_tool_call_shows_before_its_output() -> None:
    _, ticks = run_sim(uncapped(), 40)
    tool_calls = 0
    for gained in ticks:
        for (name, line), (later_name, later) in itertools.pairwise(gained):
            if line.kind == "tool":
                tool_calls += 1
                assert not (later_name == name and later.kind in {"result", "diff"})
    assert tool_calls > 0


def test_calls_count_tool_calls_not_lines() -> None:
    sim = Sim([pick_scenario(None, "prod")], uncapped(agents=2), random.Random(7))

    def tally() -> list[tuple[int, int, int]]:
        return [
            (
                agent.calls,
                sum(line.kind == "tool" for line in agent.log),
                sum(line.kind == "quip" for line in agent.log),
            )
            for agent in sim.agents
        ]

    before = tally()
    for _ in range(600):
        sim.tick(0.05)
    for (calls, tools, quips), (calls0, tools0, quips0) in zip(
        tally(), before, strict=True
    ):
        assert tools - tools0 <= calls - calls0 <= (tools - tools0) + (quips - quips0)


def test_long_command_output_collapses_like_claude_code() -> None:
    sim, _ = run_sim(uncapped(), 60)
    collapsed = 0
    for agent in sim.agents:
        log = list(agent.log)
        for before, line in itertools.pairwise(log):
            if COLLAPSED.match(line.text):
                collapsed += 1
                assert line.kind == "result"
                assert before.kind == "result"
                tool = next(
                    row
                    for row in reversed(log[: log.index(line)])
                    if row.kind == "tool"
                )
                assert tool.label == "Bash"
    assert collapsed > 0


def test_checking_off_a_todo_shows_the_updated_list() -> None:
    sim, _ = run_sim(uncapped(agents=3), 60)
    blocks = 0
    for agent in sim.agents:
        log = list(agent.log)
        texts = [todo.text for todo in agent.todos]
        for index, line in enumerate(log):
            if not (line.kind == "tool" and line.label == "Update Todos"):
                continue
            blocks += 1
            assert line.text == ""
            items = []
            for row in log[index + 1 :]:
                if row.kind != "result":
                    break
                items.append(row.text)
            assert 1 <= len(items) <= 5
            boxes = [item[:2] for item in items]
            assert set(boxes) <= {"☒ ", "☐ "}
            assert "☒ " in boxes
            assert boxes == sorted(boxes, key=lambda box: box != "☒ ")
            assert len(texts) == len(set(texts))
            names = [item[2:] for item in items]
            start = texts.index(names[0])
            assert texts[start : start + len(names)] == names
    assert blocks > 0


def test_one_todo_update_at_a_time() -> None:
    sim, _ = run_sim(
        SwarmSettings(agents=3, interns=0, log_length=None, length=4.0), 30
    )
    for agent in sim.agents:
        tools = [line for line in agent.log if line.kind == "tool"]
        for first, second in itertools.pairwise(tools):
            assert not (first.label == second.label == "Update Todos")


def test_reports_keep_acronyms_capitalized(tmp_path: Path) -> None:
    path = tmp_path / "acronyms.toml"
    path.write_text(QUIP_PACK, encoding="utf-8")
    sim = Sim(
        [load_scenario(path)], SwarmSettings(agents=3, interns=0), random.Random(2)
    )
    for _ in range(1200):
        sim.tick(0.05)
    texts = {text for _, text in sim.reports}
    assert "core.py: CI is green." in texts
    assert "core.py: I fixed it." in texts
    assert "core.py: A/B test passed." in texts
    assert not any("cI" in text or " i fixed" in text for text in texts)


# ---- the panel draws them like Claude Code -----------------------------------


def test_tools_render_under_their_claude_code_names() -> None:
    def shown(entry: LogLine) -> str:
        return render_entry(entry, 40).plain.rstrip()

    assert shown(LogLine("tool", "cache.rs", "Edit")) == "● Update(cache.rs)"
    assert shown(LogLine("tool", "TODO", "Grep")) == '● Search(pattern: "TODO")'
    assert shown(LogLine("tool", "how to scale", "WebSearch")) == (
        '● Web Search("how to scale")'
    )
    assert shown(LogLine("tool", "", "Update Todos")) == "● Update Todos"
    assert shown(LogLine("tool", "cargo test", "Bash")) == "● Bash(cargo test)"


def test_assistant_text_gets_a_bullet() -> None:
    assert render_entry(LogLine("quip", "Paged nobody."), 30).plain.rstrip() == (
        "● Paged nobody."
    )


def test_output_lines_after_the_first_hang_under_it() -> None:
    entry = LogLine("result", "Finished in 0.4s", "dim")
    assert render_entry(entry, 30).plain.rstrip() == "  ⎿  Finished in 0.4s"
    assert render_entry(entry, 30, continued=True).plain.rstrip() == (
        "     Finished in 0.4s"
    )


def test_diff_lines_indent_under_the_summary() -> None:
    def shown(sign: str) -> str:
        return render_entry(LogLine("diff", "x = 1", sign, 42), 30).plain.rstrip()

    assert shown("+") == "       42 + x = 1"
    assert shown("-") == "       42 - x = 1"
    assert shown(" ") == "       42   x = 1"


def test_a_failed_tool_call_gets_a_red_bullet() -> None:
    entry = LogLine("tool", "cargo test", "Bash")

    def bullet_styles(*, failed: bool) -> set[str]:
        line = render_entry(entry, 30, failed=failed)
        return {str(span.style) for span in line.spans if span.start == 0}

    assert "red" in bullet_styles(failed=True)
    assert "red" not in bullet_styles(failed=False)
    assert "green" in bullet_styles(failed=False)


@pytest.mark.parametrize("seed", range(8))
def test_panels_separate_turns_with_blank_lines(seed: int) -> None:
    console = Console(width=70, height=40, force_terminal=True, color_system=None)
    sim = Sim(
        [pick_scenario(None, "prod")],
        SwarmSettings(agents=1, interns=0, length=60.0),
        random.Random(seed),
    )
    wall = Wall(sim, console)
    for _ in range(int(20 / 0.05)):
        wall.step(0.05)
    with console.capture() as capture:
        console.print(wall.render(), height=console.height)
    rows = [
        row.split("│")[1]
        for row in capture.get().splitlines()
        if row.startswith("│") and row.count("│") >= 2
    ]
    body = [row[1:].rstrip() for row in rows]
    assert body[0], "a full panel never starts on a blank separator"
    turns = [index for index, row in enumerate(body) if row.startswith("● ")]
    assert len(turns) >= 3
    for index in turns:
        if index > 0:
            assert body[index - 1] == ""
    for above, row in itertools.pairwise(body):
        assert not (above.startswith("  ⎿") and row.startswith("  ⎿"))
    for row in body:
        if re.match(r"^\s+\d+ [-+ ] ", row):
            assert row.startswith("     ")


# ---- agents work like real engineers, through real workflows ----------------


def pack_tools(key: str, seconds: float = 60) -> list[list[LogLine]]:
    settings = SwarmSettings(
        agents=4, interns=0, mode=RunMode.ENDLESS, log_length=None, length=20.0
    )
    sim = Sim([pick_scenario(None, key)], settings, random.Random(7))
    for _ in range(int(seconds / 0.05)):
        sim.tick(0.05)
    return [[line for line in agent.log if line.kind == "tool"] for agent in sim.agents]


@pytest.mark.parametrize("key", ["prod", "startup", "girlfriend", "wrapper"])
def test_agents_run_a_wide_variety_of_commands(key: str) -> None:
    commands = [
        line.text for tools in pack_tools(key) for line in tools if line.label == "Bash"
    ]
    programs = {command.split()[0] for command in commands}
    invocations = {" ".join(command.split()[:2]) for command in commands}
    assert len(programs) >= 15
    assert len(invocations) >= 35


def test_agents_commit_the_files_they_just_edited() -> None:
    committed = 0
    for tools in pack_tools("prod", seconds=90):
        edited: set[str] = set()
        for line in tools:
            if line.label == "Edit":
                edited.add(line.text)
            elif line.label == "Bash" and line.text.startswith("git add "):
                path = line.text.removeprefix("git add ").split(" &&")[0]
                committed += path in edited
    assert committed > 0


def test_a_panel_marks_failed_tool_calls_red_and_the_rest_green() -> None:
    console = Console(
        width=70, height=200, force_terminal=True, color_system="truecolor"
    )
    sim, _ = run_sim(SwarmSettings(agents=2, interns=0, log_length=60), 40, seed=3)
    wall = Wall(sim, console)
    seen = {"red": 0, "green": 0}
    for agent in sim.agents:
        log = list(agent.log)
        expected = []
        for index, line in enumerate(log):
            if line.kind != "tool" or not line.text:
                continue
            block = []
            for row in log[index + 1 :]:
                if row.kind not in {"result", "diff"}:
                    break
                block.append(row)
            if block:
                failed = any(row.label == "red" for row in block)
                expected.append("red" if failed else "green")
        rows = console.render_lines(
            AgentPanel(wall).render(agent),
            console.options.update(height=len(log) * 2 + 4),
        )
        bullets = []
        for row in rows:
            text = "".join(segment.text for segment in row)
            if "● " in text and "(" in text:
                bullet = next(s for s in row if s.text.startswith("●"))
                color = (
                    bullet.style.color.name
                    if bullet.style is not None and bullet.style.color is not None
                    else ""
                )
                bullets.append(color)
        shown = [color for color in bullets if color in {"red", "green"}]
        assert shown[-len(expected) :] == expected[-len(shown) :]
        for color in shown:
            seen[color] += 1
    assert seen["red"] > 0
    assert seen["green"] > 0
