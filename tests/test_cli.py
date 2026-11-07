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
