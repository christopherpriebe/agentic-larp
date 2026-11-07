import random
import re
from collections.abc import Callable

import pytest
from rich.console import Console
from rich.text import Text

from agentic_larp.apps import (
    SHARED_ERRORS,
    AppContext,
    Outcome,
    app_registry,
    capture_frame,
    decay,
    run_meltdown,
)
from support import FakeClock, ScriptedKeys, output

# Every fake death screen shows exactly one of these.
DEATHS = ("exited with code 137", "Kernel panic", "Your PC ran into a problem")
SUCCESS_GOODBYES = {
    "call": "says goodnight",
    "hacker": "connection closed",
    "deploy": "shipped.",
    "stonks": "closed at an all-time high",
    "dropship": "orders shipped",
    "memecoin": "100x",
    "wrapper": "passed the API bill",
    "nft": "minted out",
    "thoughtleader": "thank your barista",
    "clipfarm": "full episode got",
    "matchmaker": "ordered the same dessert",
}
# A word each app shows on screen while it runs, and one it shows when it breaks.
SIGNATURES = {
    "dropship": ("orders", "chargeback"),
    "memecoin": ("holders", "rug"),
    "wrapper": ("MRR", "rate limit"),
    "nft": ("floor", "right-click"),
    "thoughtleader": ("impressions", "authenticity"),
    "clipfarm": ("clips", "that's crazy bro"),
    "matchmaker": ("expires in", "reassigned"),
}
FRAME = ["hello world", "  agents  ", "", "ship it"]


def has_death(text: str) -> bool:
    return any(death in text for death in DEATHS)


def changed(before: list[str], after: list[str]) -> set[tuple[int, int]]:
    return {
        (row, col)
        for row, (old, new) in enumerate(zip(before, after, strict=True))
        for col, (a, b) in enumerate(zip(old, new, strict=True))
        if a != b
    }


def test_outcome_values() -> None:
    assert Outcome("success") is Outcome.SUCCESS
    assert Outcome("fail") is Outcome.FAIL


def test_app_context_defaults_to_success(console: Console) -> None:
    assert AppContext(console=console, task="t").outcome is Outcome.SUCCESS


def test_decay_of_zero_changes_nothing() -> None:
    assert decay(FRAME, 0.0, random.Random(1)) == FRAME


def test_decay_of_one_corrupts_every_visible_character() -> None:
    lines = ["abcdefghij", "klm nop", "qrstuvwxyz"]
    result = decay(lines, 1.0, random.Random(1))
    for old, new in zip(lines, result, strict=True):
        for a, b in zip(old, new, strict=True):
            if a == " ":
                assert b == " "
            else:
                assert not b.isalpha()


@pytest.mark.parametrize("amount", [0.0, 0.25, 0.5, 0.75, 1.0])
def test_decay_keeps_the_frame_shape(amount: float) -> None:
    result = decay(FRAME, amount, random.Random(3))
    assert [len(line) for line in result] == [len(line) for line in FRAME]
    for old, new in zip(FRAME, result, strict=True):
        assert [i for i, c in enumerate(old) if c == " "] == [
            i for i, c in enumerate(new) if c == " "
        ]


def test_more_decay_corrupts_a_superset() -> None:
    lines = ["the quick brown fox", "jumps over the lazy dog"] * 3
    light = changed(lines, decay(lines, 0.3, random.Random(9)))
    heavy = changed(lines, decay(lines, 0.6, random.Random(9)))
    assert light
    assert light < heavy


@pytest.mark.parametrize("amount", [-0.1, 1.1])
def test_decay_rejects_amounts_outside_zero_to_one(amount: float) -> None:
    with pytest.raises(ValueError, match="amount"):
        decay(FRAME, amount, random.Random(0))


def test_capture_frame_renders_plain_lines_at_console_size() -> None:
    small = Console(width=40, height=10, force_terminal=True, color_system=None)
    lines = capture_frame(small, Text("hello [bold]world[/]"))
    assert len(lines) == 10
    assert lines[0].startswith("hello [bold]world[/]")
    assert all(len(line) <= 40 for line in lines)


def test_meltdown_decays_cascades_dies_and_returns(
    console: Console, clock: FakeClock
) -> None:
    context = AppContext(console=console, task="t", fps=10)
    run_meltdown(context, Text("a perfectly fine app"), ["APP-SPECIFIC-ERROR"])
    text = output(console)
    assert "APP-SPECIFIC-ERROR" in text
    assert any(error in text for error in SHARED_ERRORS)
    assert has_death(text)
    assert "jk" in text
    assert 3.0 < clock.now < 15.0


def test_escape_skips_the_meltdown(
    console: Console,
    clock: FakeClock,
    make_keys: Callable[..., ScriptedKeys],
) -> None:
    context = AppContext(
        console=console, task="t", fps=10, keys=make_keys((0.5, "esc"))
    )
    run_meltdown(context, Text("frame"), ["E1"])
    assert clock.now < 3.0


def run_app(
    name: str,
    console: Console,
    outcome: Outcome,
    keys: ScriptedKeys | None = None,
    auto: float | None = None,
) -> str:
    context = AppContext(
        console=console,
        task="build a billion dollar startup",
        auto=auto,
        fps=10,
        keys=keys,
        outcome=outcome,
    )
    app_registry()[name](context)
    return output(console)


@pytest.mark.parametrize("name", sorted(SUCCESS_GOODBYES))
def test_every_app_fails_on_its_own_when_told_to(
    name: str,
    console: Console,
    clock: FakeClock,
    make_keys: Callable[..., ScriptedKeys],
) -> None:
    keys = make_keys((0.5, "x"))  # answers the call; harmless elsewhere
    text = run_app(name, console, Outcome.FAIL, keys)
    assert has_death(text)
    assert "jk" in text
    assert SUCCESS_GOODBYES[name] not in text
    assert clock.now < 60.0


@pytest.mark.parametrize("name", sorted(SUCCESS_GOODBYES))
def test_apps_succeed_by_default(
    name: str,
    console: Console,
    clock: FakeClock,
    make_keys: Callable[..., ScriptedKeys],
) -> None:
    keys = make_keys((0.5, "x"))
    context = AppContext(
        console=console,
        task="build a billion dollar startup",
        auto=12.0,
        fps=10,
        keys=keys,
    )
    app_registry()[name](context)
    text = output(console)
    assert not has_death(text)
    assert SUCCESS_GOODBYES[name] in text
    assert clock.now <= 13.0


HACKER_STAGES = (
    "SCANNING",
    "DUMPING MEMORY",
    "CRACKING PASSWORD",
    "TRACING",
    "ACCESS GRANTED",
)


def test_hacker_plays_its_stages_in_order_and_finishes_itself(
    console: Console, clock: FakeClock
) -> None:
    text = run_app("hacker", console, Outcome.SUCCESS)
    positions = [text.find(stage) for stage in HACKER_STAGES]
    assert all(p >= 0 for p in positions)
    assert positions == sorted(positions)
    assert "connection closed" in text
    assert clock.now < 60.0


def test_hacker_no_longer_types_python_source(
    console: Console, clock: FakeClock
) -> None:
    text = run_app("hacker", console, Outcome.SUCCESS)
    assert "def " not in text
    assert "import " not in text
    assert clock.now > 0


def test_mashing_keys_makes_the_hack_go_faster(
    console: Console,
    clock: FakeClock,
    make_keys: Callable[..., ScriptedKeys],
) -> None:
    run_app("hacker", console, Outcome.SUCCESS)
    calm = clock.now
    clock.now = 0.0
    mash = make_keys(*((i * 0.05, "k") for i in range(2000)))
    run_app(
        "hacker",
        Console(
            file=console.file,
            width=140,
            height=44,
            force_terminal=True,
            color_system=None,
        ),
        Outcome.SUCCESS,
        mash,
    )
    assert clock.now < calm * 0.6


def test_failed_hack_gets_traced(console: Console, clock: FakeClock) -> None:
    text = run_app("hacker", console, Outcome.FAIL)
    assert "TRACE COMPLETE" in text
    assert "ACCESS GRANTED" not in text.split("TRACE COMPLETE")[-1]
    assert has_death(text)
    assert clock.now < 60.0


def test_failing_call_answers_itself_when_nobody_picks_up(
    console: Console, clock: FakeClock
) -> None:
    text = run_app("call", console, Outcome.FAIL)
    assert has_death(text)
    assert "says goodnight" not in text
    assert clock.now < 60.0


@pytest.mark.parametrize(
    ("name", "schedule"),
    [
        ("deploy", ((1.0, "esc"),)),
        ("stonks", ((1.0, "esc"),)),
        ("call", ((0.5, "x"), (1.5, "esc"))),
        ("hacker", ((1.0, "esc"),)),
        ("dropship", ((1.0, "esc"),)),
        ("memecoin", ((1.0, "esc"),)),
        ("wrapper", ((1.0, "esc"),)),
        ("nft", ((1.0, "esc"),)),
        ("thoughtleader", ((1.0, "esc"),)),
        ("clipfarm", ((1.0, "esc"),)),
        ("matchmaker", ((1.0, "esc"),)),
    ],
)
def test_escaping_before_the_break_skips_the_meltdown(
    name: str,
    schedule: tuple[tuple[float, str], ...],
    console: Console,
    clock: FakeClock,
    make_keys: Callable[..., ScriptedKeys],
) -> None:
    text = run_app(name, console, Outcome.FAIL, make_keys(*schedule))
    assert not has_death(text)
    assert "jk" not in text
    assert clock.now < 10.0


def test_failing_hacker_never_promises_access(
    console: Console, clock: FakeClock
) -> None:
    text = run_app("hacker", console, Outcome.FAIL)
    assert "access granted" not in text.lower().split("trace complete")[0]
    assert clock.now > 0


@pytest.mark.parametrize("name", sorted(SIGNATURES))
def test_grift_apps_show_their_hustle(
    name: str, console: Console, clock: FakeClock
) -> None:
    context = AppContext(console=console, task="get rich quick", auto=8.0, fps=10)
    app_registry()[name](context)
    text = output(console).lower()
    assert SIGNATURES[name][0].lower() in text
    assert SIGNATURES[name][1].lower() not in text
    assert clock.now <= 9.0


@pytest.mark.parametrize("name", sorted(SIGNATURES))
def test_grift_apps_fail_in_their_own_way(
    name: str, console: Console, clock: FakeClock
) -> None:
    text = run_app(name, console, Outcome.FAIL)
    assert SIGNATURES[name][1].lower() in text.lower()
    assert has_death(text)
    assert clock.now < 60.0


def test_failing_hacker_footer_tells_the_truth(
    console: Console, clock: FakeClock
) -> None:
    text = run_app("hacker", console, Outcome.FAIL)
    assert "tab: access denied" in text
    assert "tab: nothing" not in text
    assert clock.now > 0


def test_hanging_up_ends_the_call_promptly(
    console: Console,
    clock: FakeClock,
    make_keys: Callable[..., ScriptedKeys],
) -> None:
    keys = make_keys(
        (0.5, "x"),
        *((1.0, key) for key in "i love you"),
        (1.0, "enter"),
        (1.1, "esc"),
    )
    text = run_app("call", console, Outcome.SUCCESS, keys)
    assert "says goodnight" in text
    # her reply to "i love you" was queued, then dropped by the hang-up
    assert "i love you too" not in text
    assert "writing that to memory.cpp" not in text
    assert clock.now < 10.0


def test_task_text_is_never_read_as_markup(console: Console, clock: FakeClock) -> None:
    for name in sorted(SIGNATURES):
        context = AppContext(
            console=console, task="mint an nft [/] of [cat]", auto=2.0, fps=10
        )
        app_registry()[name](context)
    assert "[/] of [cat]" in output(console)
    assert clock.now > 0


def test_memecoin_price_stays_finite_however_long_it_runs(
    console: Console,
    clock: FakeClock,
    make_keys: Callable[..., ScriptedKeys],
) -> None:
    keys = make_keys(*((i * 0.2, "m") for i in range(1500)))
    context = AppContext(
        console=console, task="launch a memecoin", auto=300.0, fps=10, keys=keys
    )
    app_registry()["memecoin"](context)
    text = output(console).lower()
    assert "inf" not in text.replace("info", "")
    assert "nan" not in text
    assert clock.now >= 300.0


def test_wrapper_bill_stays_readable_when_it_explodes(
    console: Console, clock: FakeClock
) -> None:
    text = run_app("wrapper", console, Outcome.FAIL)
    assert not re.search(r"\$[\d,]{16,}", text)
    assert "rate limit" in text.lower()
    assert clock.now < 60.0


def test_matchmaker_never_borrows_the_episode_reveal(
    console: Console, clock: FakeClock
) -> None:
    context = AppContext(console=console, task="find my soulmate", auto=8.0, fps=10)
    app_registry()["matchmaker"](context)
    text = output(console).lower()
    assert "rebel" not in text
    assert "99.8" not in text
    assert clock.now > 0
