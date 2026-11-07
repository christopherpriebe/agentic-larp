import importlib.metadata
import random
from collections.abc import Callable
from dataclasses import dataclass, field

import pytest
from rich.console import Console

from agentic_larp import (
    END,
    FLOW,
    STAGE_ENTRY_POINT_GROUP,
    KeySource,
    LarpError,
    ReceiptStage,
    Session,
    Sim,
    Stage,
    SwarmSettings,
    main,
    pick_scenario,
    run_flow,
    stage_registry,
)
from agentic_larp.apps import AppContext
from support import FakeClock, ScriptedKeys, output


def make_session(
    console: Console,
    *,
    auto: float | None = None,
    pace: float = 1.0,
    fps: int = 20,
    keys: KeySource | None = None,
) -> tuple[Session, Sim]:
    sim = Sim(
        [pick_scenario(None, "prod")],
        SwarmSettings(agents=4, interns=0),
        random.Random(4),
    )
    session = Session(
        console=console,
        task=sim.task,
        sim=sim,
        rng=random.Random(4),
        auto=auto,
        pace=pace,
        fps=fps,
        keys=keys,
    )
    return session, sim


@dataclass
class Recorder:
    """A stage that notes it ran and returns a scripted next step."""

    name: str
    log: list[str]
    result: str | None = None

    def run(self, session: Session) -> str | None:
        self.log.append(self.name)
        session.console.print(f"stage {self.name}")
        return self.result


@dataclass
class Script:
    log: list[str] = field(default_factory=list)
    results: dict[str, str | None] = field(default_factory=dict)

    def stages(self, *names: str) -> dict[str, Callable[[], Stage]]:
        return {
            name: (lambda name=name: Recorder(name, self.log, self.results.get(name)))
            for name in names
        }


def test_the_flow_is_the_agentic_loop() -> None:
    assert FLOW == ("plan", "work", "wrap", "ready", "ship", "launch", "receipt")


def test_run_flow_plays_stages_in_order(console: Console) -> None:
    script = Script()
    assert (
        run_flow(
            make_session(console)[0], ("a", "b", "c"), script.stages("a", "b", "c")
        )
        == 0
    )
    assert script.log == ["a", "b", "c"]


def test_a_stage_can_jump_to_a_named_stage(console: Console) -> None:
    script = Script(results={"a": "c"})
    run_flow(make_session(console)[0], ("a", "b", "c"), script.stages("a", "b", "c"))
    assert script.log == ["a", "c"]


def test_a_stage_can_jump_to_a_stage_outside_the_flow(console: Console) -> None:
    script = Script(results={"a": "side", "side": END})
    run_flow(make_session(console)[0], ("a", "b"), script.stages("a", "b", "side"))
    assert script.log == ["a", "side"]


def test_end_stops_the_session(console: Console) -> None:
    script = Script(results={"b": END})
    run_flow(make_session(console)[0], ("a", "b", "c"), script.stages("a", "b", "c"))
    assert script.log == ["a", "b"]


def test_run_flow_returns_the_session_exit_code(console: Console) -> None:
    class Failing:
        def run(self, session: Session) -> str | None:
            session.exit_code = 7
            return None

    assert run_flow(make_session(console)[0], ("x",), {"x": Failing}) == 7


def test_an_unregistered_flow_entry_is_an_error(console: Console) -> None:
    script = Script()
    with pytest.raises(LarpError, match="'nope'"):
        run_flow(make_session(console)[0], ("a", "nope"), script.stages("a"))
    assert script.log == []


def test_jumping_to_an_unregistered_stage_is_an_error(console: Console) -> None:
    script = Script(results={"a": "ghost"})
    with pytest.raises(LarpError, match="'ghost'"):
        run_flow(make_session(console)[0], ("a",), script.stages("a"))


def test_registry_has_every_builtin_stage() -> None:
    registry = stage_registry()
    assert set(FLOW) | {"abandon"} <= set(registry)
    for factory in registry.values():
        assert callable(factory().run)


@dataclass
class FakeEntryPoint:
    name: str
    target: object

    def load(self) -> object:
        return self.target


def test_plugin_stages_join_the_registry_and_can_run(
    console: Console, monkeypatch: pytest.MonkeyPatch
) -> None:
    log: list[str] = []

    class Review:
        def run(self, session: Session) -> str | None:
            log.append("review")
            session.console.print("LGTM, said nobody")
            return END

    real = importlib.metadata.entry_points

    def fake_entry_points(*, group: str) -> object:
        if group == STAGE_ENTRY_POINT_GROUP:
            return [FakeEntryPoint("review", Review)]
        return real(group=group)

    monkeypatch.setattr(importlib.metadata, "entry_points", fake_entry_points)
    registry = stage_registry()
    assert registry["review"] is Review
    session = make_session(console)[0]
    assert run_flow(session, ("review", "receipt"), registry) == 0
    assert log == ["review"]
    assert "✓ shipped" not in output(console)


def test_the_receipt_comes_after_the_app(console: Console) -> None:
    session, sim = make_session(console)

    class FakeLaunch:
        def run(self, session: Session) -> str | None:
            session.console.print("APP RAN")
            return None

    run_flow(
        session, ("launch", "receipt"), {"launch": FakeLaunch, "receipt": ReceiptStage}
    )
    text = output(console)
    assert "✓ shipped" in text
    assert text.index("APP RAN") < text.index("✓ shipped")
    assert f"{len(sim.agents)} agents" in text


def test_the_receipt_says_nothing_without_a_swarm(console: Console) -> None:
    session = Session(console=console, task="t", sim=None, rng=random.Random(0))
    run_flow(session, ("receipt",), {"receipt": ReceiptStage})
    assert "shipped" not in output(console)


def test_app_context_carries_the_session(console: Console) -> None:
    session, _ = make_session(console, auto=3.0, fps=12)
    context = session.app_context()
    assert isinstance(context, AppContext)
    assert context.console is console
    assert context.task == session.task
    assert context.auto == 3.0
    assert context.fps == 12


def test_session_defaults() -> None:
    session = Session(console=Console(), task="t", sim=None, rng=random.Random(0))
    assert session.app == "none"
    assert session.then is None
    assert session.auto is None
    assert session.pace == 1.0
    assert session.flags == {}
    assert session.exit_code == 0


def test_the_default_flow_runs_end_to_end(console: Console, clock: FakeClock) -> None:
    session, sim = make_session(console, auto=1.0)
    assert run_flow(session) == 0
    assert "✓ shipped" in output(console)
    assert sim.is_all_done
    assert clock.now > 1.0


def test_escape_abandons_the_run(console: Console, clock: FakeClock) -> None:
    keys = ScriptedKeys(clock, [(0.5, "a"), (1.0, "esc"), (1.0, "esc")])
    session, _ = make_session(console, keys=keys)
    assert run_flow(session) == 0
    text = output(console)
    assert "nothing was built" in text
    assert "✓ shipped" not in text
    assert 1.0 <= clock.now < 2.0


def test_pace_speeds_up_the_whole_show(console: Console, clock: FakeClock) -> None:
    session, _ = make_session(console, auto=5.0, pace=10.0)
    assert run_flow(session) == 0
    assert clock.now < 3.0


def test_cli_prints_the_receipt_after_the_app(
    capsys: pytest.CaptureFixture[str], clock: FakeClock
) -> None:
    assert main(["-s", "hacker", "--auto", "1", "--speed", "4", "-i", "0"]) == 0
    text = capsys.readouterr().out
    assert text.index("connection closed") < text.index("✓ shipped")
    assert clock.now > 1.0


def test_unknown_app_after_shipping_still_returns_two(
    capsys: pytest.CaptureFixture[str], clock: FakeClock
) -> None:
    assert main(["-s", "prod", "--auto", "1", "--speed", "4", "--app", "nope"]) == 2
    text = capsys.readouterr().out
    assert "no app called 'nope'" in text
    assert clock.now > 1.0


def test_a_printing_stage_after_a_screen_stage_is_not_wiped(
    console: Console, clock: FakeClock
) -> None:
    alt_screen: list[bool] = []

    class Note:
        def run(self, session: Session) -> str | None:
            alt_screen.append(session.console.is_alt_screen)
            session.console.print("AFTER THE WALL")
            return END

    session, _ = make_session(console, auto=0.5)
    registry = stage_registry()
    run_flow(session, ("work", "note"), {"work": registry["work"], "note": Note})
    assert alt_screen == [False]
    assert "AFTER THE WALL" in output(console)
    assert clock.now > 0.5


def test_keys_typed_past_a_stage_change_reach_the_next_stage(
    console: Console, clock: FakeClock
) -> None:
    burst = [*"ship it", "enter", *"draft"]
    keys = ScriptedKeys(clock, [(0.5, key) for key in burst])
    session, sim = make_session(console, keys=keys)
    registry = stage_registry()
    run_flow(
        session, ("work", "wrap"), {name: registry[name] for name in ("work", "wrap")}
    )
    assert sim.is_all_done
    assert session.wall is not None
    assert session.wall.buffer == "draft"


def test_a_wall_stage_needs_a_swarm(console: Console) -> None:
    session = Session(console=console, task="t", sim=None, rng=random.Random(0))
    with pytest.raises(LarpError, match="swarm"):
        run_flow(session, ("work",))


def test_play_none_is_not_an_app(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--play", "none"]) == 2
    assert "no app called 'none'" in capsys.readouterr().out
