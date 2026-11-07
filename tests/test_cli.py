from pathlib import Path

import pytest

from agentic_larp import build_parser, fit_agents, main
from support import FakeClock


def test_list_shows_scenarios_and_apps(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--list"]) == 0
    text = capsys.readouterr().out
    for name in (
        "girlfriend",
        "startup",
        "hacker",
        "prod",
        "generic",
        "call",
        "stonks",
        "deploy",
    ):
        assert name in text


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit, match="0"):
        main(["--version"])
    assert capsys.readouterr().out.startswith("agentic-larp ")


def test_parser_reads_a_multi_word_task() -> None:
    args = build_parser().parse_args(
        ["build", "uber", "for", "cats", "-n", "3", "--speed", "2"]
    )
    assert args.task == ["build", "uber", "for", "cats"]
    assert args.agents == 3
    assert args.speed == 2.0


@pytest.mark.parametrize(
    ("width", "height", "has_interns", "expected"),
    [(80, 24, True, 2), (120, 40, True, 9), (120, 40, False, 9), (300, 100, True, 12)],
)
def test_fit_agents_fills_the_terminal_within_bounds(
    width: int,
    height: int,
    *,
    has_interns: bool,
    expected: int,
) -> None:
    assert fit_agents(width, height, has_interns=has_interns) == expected


def test_non_interactive_run_ships_itself(
    capsys: pytest.CaptureFixture[str],
    clock: FakeClock,
) -> None:
    assert (
        main(
            [
                "uber",
                "for",
                "cats",
                "--app",
                "none",
                "--seed",
                "1",
                "--speed",
                "4",
                "-i",
                "0",
            ]
        )
        == 0
    )
    assert "✓ shipped uber for cats" in capsys.readouterr().out
    assert clock.now > 1.0


def test_run_launches_the_scenario_app(
    capsys: pytest.CaptureFixture[str], clock: FakeClock
) -> None:
    assert main(["-s", "startup", "--auto", "1", "--speed", "4", "--seed", "2"]) == 0
    assert clock.now > 1.0
    assert "closed at an all-time high" in capsys.readouterr().out


def test_then_runs_a_real_command_after_shipping(
    capsys: pytest.CaptureFixture[str],
    clock: FakeClock,
) -> None:
    assert main(["-s", "prod", "--auto", "1", "--speed", "4", "--then", "exit 3"]) == 3
    assert clock.now > 1.0
    assert "✓ shipped" in capsys.readouterr().out


def test_play_launches_an_app_directly(
    capsys: pytest.CaptureFixture[str], clock: FakeClock
) -> None:
    assert main(["--play", "hacker", "--auto", "1"]) == 0
    assert clock.now > 1.0
    assert "connection closed" in capsys.readouterr().out


def test_play_rejects_an_unknown_app(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--play", "minesweeper"]) == 2
    assert "no app called 'minesweeper'" in capsys.readouterr().out


def test_ctrl_c_exits_politely(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def interrupt(*_: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr("time.sleep", interrupt)
    assert main(["--play", "stonks", "--auto", "5"]) == 130
    assert "ctrl-c" in capsys.readouterr().out


PACK = """
[pack]
key = "zebra"
task = "build a zebra"
keywords = ["zebra"]
app = "stonks"

[areas]
stripes = ["stripes.py"]
"""


def test_list_includes_packs_from_the_config_dir(
    capsys: pytest.CaptureFixture[str],
    config_home: Path,
) -> None:
    (config_home / "zebra.toml").write_text(PACK, encoding="utf-8")
    assert main(["--list"]) == 0
    assert "zebra" in capsys.readouterr().out


def test_broken_config_pack_warns_and_is_skipped(
    capsys: pytest.CaptureFixture[str],
    config_home: Path,
) -> None:
    (config_home / "broken.toml").write_text("[pack", encoding="utf-8")
    (config_home / "zebra.toml").write_text(PACK, encoding="utf-8")
    assert main(["--list"]) == 0
    text = capsys.readouterr().out
    assert "warning" in text
    assert "broken.toml" in text
    assert "zebra" in text


def test_broken_pack_flag_is_an_error(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    broken = tmp_path / "broken.toml"
    broken.write_text("[pack", encoding="utf-8")
    assert main(["--pack", str(broken), "--list"]) == 2
    assert "broken.toml" in capsys.readouterr().out


def test_pack_flag_runs_a_custom_pack_end_to_end(
    capsys: pytest.CaptureFixture[str],
    clock: FakeClock,
    tmp_path: Path,
) -> None:
    pack = tmp_path / "zebra.toml"
    pack.write_text(PACK, encoding="utf-8")
    args = [
        "--pack",
        str(pack),
        "-s",
        "zebra",
        "--auto",
        "1",
        "--speed",
        "4",
        "--app",
        "none",
    ]
    assert main(args) == 0
    assert "✓ shipped build a zebra" in capsys.readouterr().out
    assert clock.now > 1.0


def test_repeated_scenario_flags_mix_packs(
    capsys: pytest.CaptureFixture[str],
    clock: FakeClock,
) -> None:
    args = [
        "-s",
        "hacker",
        "-s",
        "girlfriend",
        "-n",
        "4",
        "--auto",
        "1",
        "--speed",
        "4",
        "--app",
        "none",
    ]
    assert main(args) == 0
    assert "✓ shipped hack the mainframe · 4 agents" in capsys.readouterr().out
    assert clock.now > 1.0


def test_unknown_scenario_is_an_error(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["-s", "nope", "--auto", "1"]) == 2
    assert "no pack called 'nope'" in capsys.readouterr().out


def test_grid_flag_sets_the_agent_count(
    capsys: pytest.CaptureFixture[str],
    clock: FakeClock,
) -> None:
    assert (
        main(
            [
                "-s",
                "prod",
                "--grid",
                "2x2",
                "--auto",
                "1",
                "--speed",
                "4",
                "--app",
                "none",
            ]
        )
        == 0
    )
    assert "· 4 agents ·" in capsys.readouterr().out
    assert clock.now > 1.0


def test_grid_with_more_agents_runs_them_all(
    capsys: pytest.CaptureFixture[str],
    clock: FakeClock,
) -> None:
    args = [
        "-s",
        "prod",
        "--grid",
        "2x1",
        "-n",
        "9",
        "--auto",
        "1",
        "--speed",
        "4",
        "--app",
        "none",
    ]
    assert main(args) == 0
    assert "· 9 agents ·" in capsys.readouterr().out
    assert clock.now > 1.0


def test_bad_grid_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit, match="2"):
        main(["--grid", "0x2"])
    assert "COLSxROWS" in capsys.readouterr().err


def test_pack_text_is_shown_literally_not_as_markup(
    capsys: pytest.CaptureFixture[str],
    config_home: Path,
    clock: FakeClock,
) -> None:
    (config_home / "brackets.toml").write_text(
        PACK.replace('key = "zebra"', 'key = "brackets"').replace(
            'task = "build a zebra"', 'task = "fix [/] the [beta] bug"'
        ),
        encoding="utf-8",
    )
    assert main(["--list"]) == 0
    assert "fix [/] the [beta] bug" in capsys.readouterr().out
    assert main(["-s", "brackets", "--auto", "1", "--speed", "4", "--app", "none"]) == 0
    assert "✓ shipped fix [/] the [beta] bug" in capsys.readouterr().out
    assert clock.now > 1.0


@pytest.mark.parametrize("speed", ["0", "-1", "nan", "inf", "fast"])
def test_bad_speed_is_a_usage_error(
    capsys: pytest.CaptureFixture[str], speed: str
) -> None:
    with pytest.raises(SystemExit, match="2"):
        main(["--speed", speed])
    assert "--speed" in capsys.readouterr().err


@pytest.mark.parametrize("agents", ["0", "-3"])
def test_agent_count_must_be_positive(
    capsys: pytest.CaptureFixture[str], agents: str
) -> None:
    with pytest.raises(SystemExit, match="2"):
        main(["-n", agents])
    assert "-n/--agents" in capsys.readouterr().err


def test_ending_flag_reaches_the_app(
    capsys: pytest.CaptureFixture[str], clock: FakeClock
) -> None:
    assert main(["--play", "stonks", "--flag", "ending=meltdown"]) == 0
    text = capsys.readouterr().out
    assert "jk" in text
    assert "closed at an all-time high" not in text
    assert clock.now > 1.0


def test_ending_flag_reaches_the_app_after_a_show(
    capsys: pytest.CaptureFixture[str], clock: FakeClock
) -> None:
    args = ["-s", "prod", "--auto", "1", "--speed", "4", "--flag", "ending=meltdown"]
    assert main(args) == 0
    text = capsys.readouterr().out
    assert "jk" in text
    assert "if anything breaks, it was the intern" not in text
    assert clock.now > 1.0


def test_apps_succeed_unless_told_otherwise(
    capsys: pytest.CaptureFixture[str], clock: FakeClock
) -> None:
    assert main(["--play", "stonks", "--auto", "1"]) == 0
    text = capsys.readouterr().out
    assert "closed at an all-time high" in text
    assert "jk" not in text
    assert clock.now > 1.0


@pytest.mark.parametrize("args", [["--fail"], ["--outcome", "fail"]])
def test_the_old_outcome_flags_are_gone(
    capsys: pytest.CaptureFixture[str], args: list[str]
) -> None:
    with pytest.raises(SystemExit, match="2"):
        main(["--play", "stonks", *args])
    assert "unrecognized arguments" in capsys.readouterr().err


@pytest.mark.parametrize("value", ["ending", "=meltdown", ""])
def test_a_flag_needs_key_equals_value(
    capsys: pytest.CaptureFixture[str], value: str
) -> None:
    with pytest.raises(SystemExit, match="2"):
        main(["--play", "stonks", "--flag", value])
    assert "--flag" in capsys.readouterr().err


@pytest.mark.parametrize("play", [True, False])
def test_an_unknown_ending_is_rejected_up_front(
    capsys: pytest.CaptureFixture[str], clock: FakeClock, *, play: bool
) -> None:
    run = ["--play", "stonks"] if play else ["-s", "prod", "--auto", "1"]
    assert main([*run, "--flag", "ending=nope"]) == 2
    assert "'nope'" in capsys.readouterr().out
    assert clock.now == 0.0


def test_flags_parse_into_key_value_pairs() -> None:
    args = build_parser().parse_args(["--flag", "mood=chaotic", "--flag", "x=1=2"])
    assert args.flags == [("mood", "chaotic"), ("x", "1=2")]
    assert build_parser().parse_args([]).flags == []


def test_flag_keys_and_values_are_trimmed() -> None:
    args = build_parser().parse_args(["--flag", " ending = meltdown "])
    assert args.flags == [("ending", "meltdown")]


def test_a_repeated_flag_keeps_the_last_value(
    capsys: pytest.CaptureFixture[str], clock: FakeClock
) -> None:
    args = ["--play", "stonks", "--auto", "1"]
    assert main([*args, "--flag", "ending=meltdown", "--flag", "ending=success"]) == 0
    assert "closed at an all-time high" in capsys.readouterr().out
    assert clock.now > 0


def test_a_bad_ending_is_rejected_even_with_list(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--list", "--flag", "ending=nope"]) == 2
    assert "'nope'" in capsys.readouterr().out


def test_failing_call_finishes_without_a_keyboard(
    capsys: pytest.CaptureFixture[str], clock: FakeClock
) -> None:
    assert main(["--play", "call", "--flag", "ending=meltdown"]) == 0
    assert "jk" in capsys.readouterr().out
    assert clock.now < 60.0
