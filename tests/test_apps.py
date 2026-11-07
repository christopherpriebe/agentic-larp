from collections.abc import Callable

import pytest
from rich.console import Console, RenderableType
from rich.text import Text

from agentic_larp.apps import AppContext, app_registry, run_loop
from support import FakeClock, ScriptedKeys, output


def run_app(
    name: str,
    console: Console,
    keys: ScriptedKeys | None = None,
    auto: float | None = None,
) -> str:
    app_registry()[name](
        AppContext(
            console=console,
            task="build a billion dollar startup",
            auto=auto,
            fps=10,
            keys=keys,
        )
    )
    return output(console)


def test_registry_has_every_builtin_with_a_description() -> None:
    apps = app_registry()
    assert {"call", "hacker", "deploy", "stonks"} <= set(apps)
    assert all(app.description for app in apps.values())


def test_call_rings_talks_and_hangs_up(
    console: Console,
    clock: FakeClock,
    make_keys: Callable[..., ScriptedKeys],
) -> None:
    keys = make_keys(
        (1.0, "x"),  # answer
        *((2.0, key) for key in "hi there?"),
        (2.0, "backspace"),
        (2.0, "enter"),
        (2.1, "enter"),  # empty line says nothing
        *((3.0, key) for key in "i love you"),
        (3.0, "enter"),
        (40.0, "esc"),  # hang up after some idle chatter
    )
    text = run_app("call", console, keys)
    assert "says goodnight" in text
    assert clock.now > 40.0


def test_declining_the_call_ends_quietly(
    console: Console,
    make_keys: Callable[..., ScriptedKeys],
) -> None:
    text = run_app("call", console, make_keys((0.5, "esc")))
    assert "says goodnight" not in text


def test_hacker_types_flashes_banners_and_logs_off(
    console: Console,
    make_keys: Callable[..., ScriptedKeys],
) -> None:
    keys = make_keys(
        *((0.1 * i, "k") for i in range(30)),
        (3.5, "tab"),
        (7.0, "`"),
        (12.0, "esc"),
    )
    assert "connection closed" in run_app("hacker", console, keys)


def test_hacker_demo_mode_types_by_itself(console: Console, clock: FakeClock) -> None:
    assert "connection closed" in run_app("hacker", console, auto=5.0)
    assert clock.now > 5.0


def test_deploy_rolls_out_everywhere_then_exits_on_a_key(
    console: Console,
    clock: FakeClock,
    make_keys: Callable[..., ScriptedKeys],
) -> None:
    keys = make_keys(*((0.2 * i, "a") for i in range(10)), (90.0, "x"))
    assert "shipped." in run_app("deploy", console, keys)
    assert clock.now >= 90.0


def test_deploy_can_be_aborted(
    console: Console, make_keys: Callable[..., ScriptedKeys]
) -> None:
    assert "shipped." in run_app("deploy", console, make_keys((1.0, "esc")))


def test_stonks_only_go_up(
    console: Console, make_keys: Callable[..., ScriptedKeys]
) -> None:
    keys = make_keys(*((0.1 * i, "m") for i in range(40)), (8.0, "esc"))
    assert "$BDS closed at an all-time high" in run_app("stonks", console, keys)


class CountdownScreen:
    def __init__(self, frames: int) -> None:
        self.frames = frames
        self.keys: list[str] = []

    def render(self) -> RenderableType:
        return Text(f"{self.frames} frames left")

    def on_key(self, key: str) -> bool:
        self.keys.append(key)
        return key != "q"

    def tick(self, dt: float) -> bool:
        assert dt >= 0
        self.frames -= 1
        return self.frames > 0


@pytest.mark.parametrize(
    ("schedule", "auto", "expected"),
    [
        ((), None, (0, [])),  # the screen ends itself
        (((0.25, "a"), (0.5, "q")), None, (15, ["a", "q"])),  # a key ends it
        ((), 0.5, (13, [])),  # demo mode ends it after the frame at 0.6s
    ],
)
def test_run_loop_stops_on_screen_key_or_timeout(
    console: Console,
    make_keys: Callable[..., ScriptedKeys],
    schedule: tuple[tuple[float, str], ...],
    auto: float | None,
    expected: tuple[int, list[str]],
) -> None:
    frames_left, keys_seen = expected
    screen = CountdownScreen(20)
    context = AppContext(
        console=console, task="t", auto=auto, fps=10, keys=make_keys(*schedule)
    )
    run_loop(context, screen)
    assert screen.keys == keys_seen
    assert screen.frames == frames_left
