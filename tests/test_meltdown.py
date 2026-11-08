import math
import random
import re
from collections.abc import Callable
from typing import Any

import pytest
from rich.console import Console
from rich.text import Text

import agentic_larp
import agentic_larp.apps
from agentic_larp import InvalidValueError, LarpError
from agentic_larp.apps import AppContext, app_registry
from agentic_larp.meltdown import (
    BLUE_SCREEN,
    DEATHS,
    ENDING_FLAG,
    EXIT_137,
    KERNEL_PANIC,
    SHARED_ERRORS,
    DeathScreen,
    Ending,
    Meltdown,
    MeltdownScreen,
    capture_frame,
    check_ending,
    decay,
    is_doomed,
    run_meltdown,
)
from support import FakeClock, ScriptedKeys, output

# Every shared fake death screen shows exactly one of these.
DEATH_MARKERS = ("exited with code 137", "Kernel panic", "Your PC ran into a problem")
DEFAULT_REVEAL = Meltdown().reveal
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


def untyped(value: object) -> Any:  # noqa: ANN401 - hands a wrongly typed value to runtime validation
    return value


def has_death(text: str) -> bool:
    return any(death in text for death in DEATH_MARKERS)


def changed(before: list[str], after: list[str]) -> set[tuple[int, int]]:
    return {
        (row, col)
        for row, (old, new) in enumerate(zip(before, after, strict=True))
        for col, (a, b) in enumerate(zip(old, new, strict=True))
        if a != b
    }


def test_outcome_is_gone() -> None:
    assert not hasattr(agentic_larp.apps, "Outcome")
    assert not hasattr(agentic_larp, "Outcome")
    assert not hasattr(agentic_larp.apps, "run_meltdown")


def test_app_context_has_flags_and_its_own_rng(console: Console) -> None:
    first = AppContext(console=console, task="t")
    second = AppContext(console=console, task="t")
    assert dict(first.flags) == {}
    assert isinstance(first.rng, random.Random)
    assert first.rng is not second.rng


def doom(ending: str | None, console: Console) -> bool:
    flags = {} if ending is None else {ENDING_FLAG: ending}
    return is_doomed(AppContext(console=console, task="t", flags=flags))


def test_only_the_ending_flag_dooms_an_app(console: Console) -> None:
    assert ENDING_FLAG == "ending"
    assert doom("meltdown", console)
    assert not doom("success", console)
    assert not doom(None, console)


def test_doom_never_depends_on_chance(console: Console) -> None:
    for seed in range(200):
        context = AppContext(console=console, task="t", rng=random.Random(seed))
        assert not is_doomed(context)


@pytest.mark.parametrize("ending", ["meltdwn", "", "MELTDOWN?", "fail"])
def test_an_unknown_ending_is_an_error_naming_it(ending: str, console: Console) -> None:
    with pytest.raises(LarpError, match=re.escape(repr(ending))):
        doom(ending, console)


def test_death_screens_are_public_data() -> None:
    assert DEATHS == (EXIT_137, KERNEL_PANIC, BLUE_SCREEN)
    assert all(isinstance(death, DeathScreen) and death.lines for death in DEATHS)
    assert len(SHARED_ERRORS) >= 10


@pytest.mark.parametrize(
    ("make", "message"),
    [
        pytest.param(lambda: Meltdown(decay_seconds=-1.0), "decay", id="decay"),
        pytest.param(
            lambda: Meltdown(cascade_seconds=math.nan), "cascade", id="cascade"
        ),
        pytest.param(lambda: Meltdown(death_seconds=math.inf), "death", id="death"),
        pytest.param(lambda: Meltdown(shared=-1), "shared", id="shared-negative"),
        pytest.param(lambda: Meltdown(shared=10_000), "shared", id="shared-too-many"),
        pytest.param(
            lambda: Meltdown(shared=untyped(2.5)), "shared", id="shared-float"
        ),
        pytest.param(lambda: Meltdown(shared=True), "shared", id="shared-bool"),
        pytest.param(lambda: Meltdown(deaths=()), "death screen", id="deaths-empty"),
        pytest.param(
            lambda: Meltdown(deaths=untyped(("oops",))),
            "death screen",
            id="deaths-type",
        ),
    ],
)
def test_meltdown_rejects_bad_settings(
    make: Callable[[], Meltdown], message: str
) -> None:
    with pytest.raises(LarpError, match=message):
        make()


def test_the_ending_values_are_public() -> None:
    assert [*Ending] == ["meltdown", "success"]


def test_the_reveal_prints_literally(console: Console, clock: FakeClock) -> None:
    context = AppContext(console=console, task="t", fps=10)
    run_meltdown(context, Text("frame"), Meltdown(reveal="jk :fire: [bold]x[/]"))
    assert output(console).rstrip().endswith("jk :fire: [bold]x[/]")
    assert clock.now > 0


def plain_text(screen: MeltdownScreen) -> str:
    console = Console(width=100, height=20, force_terminal=True, color_system=None)
    with console.capture() as capture:
        console.print(screen.render(), height=20)
    return capture.get()


def play_screen(screen: MeltdownScreen, seconds: float, dt: float = 0.05) -> list[str]:
    frames = []
    for _ in range(int(seconds / dt)):
        if not screen.tick(dt):
            break
        frames.append(plain_text(screen))
    return frames


CUSTOM = Meltdown(
    errors=("CARD DECLINED BY THE UNIVERSE",),
    shared=0,
    deaths=(DeathScreen(("PAYMENT FAILED", "please try again never"), "white on red"),),
    reveal="jk. the card was fake too.",
    note="(no cards were harmed)",
    decay_seconds=1.0,
    cascade_seconds=1.0,
    death_seconds=1.0,
)


def test_a_custom_meltdown_plays_its_own_errors_death_and_reveal() -> None:
    screen = MeltdownScreen(FRAME, CUSTOM, random.Random(2))
    text = "\n".join(play_screen(screen, 10.0))
    assert "CARD DECLINED BY THE UNIVERSE" in text
    assert not any(error in text for error in SHARED_ERRORS)
    assert "PAYMENT FAILED" in text
    assert not has_death(text)
    assert "jk. the card was fake too." in text
    assert "(no cards were harmed)" in text


def test_meltdown_length_is_the_sum_of_its_phases() -> None:
    screen = MeltdownScreen(FRAME, CUSTOM, random.Random(2))
    elapsed = 0.0
    while screen.tick(0.05):
        elapsed += 0.05
    # decay + cascade + death, then the reveal holds for one more second
    assert 3.9 <= elapsed <= 4.1


def test_escape_jumps_to_the_reveal_and_a_second_escape_leaves() -> None:
    screen = MeltdownScreen(FRAME, CUSTOM, random.Random(2))
    screen.tick(0.1)
    assert screen.on_key("esc")
    screen.tick(0.05)
    assert "jk. the card was fake too." in plain_text(screen)
    assert not screen.on_key("esc")


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
    run_meltdown(
        context, Text("a perfectly fine app"), Meltdown(errors=("APP-SPECIFIC-ERROR",))
    )
    text = output(console)
    assert "APP-SPECIFIC-ERROR" in text
    assert any(error in text for error in SHARED_ERRORS)
    assert has_death(text)
    assert text.rstrip().endswith(DEFAULT_REVEAL)
    assert 3.0 < clock.now < 15.0


def test_escape_skips_the_meltdown(
    console: Console,
    clock: FakeClock,
    make_keys: Callable[..., ScriptedKeys],
) -> None:
    context = AppContext(
        console=console, task="t", fps=10, keys=make_keys((0.5, "esc"))
    )
    run_meltdown(context, Text("frame"), Meltdown(errors=("E1",)))
    assert clock.now < 3.0


MELTDOWN = "meltdown"
SUCCESS = "success"


def run_app(
    name: str,
    console: Console,
    ending: str,
    keys: ScriptedKeys | None = None,
    auto: float | None = None,
) -> str:
    context = AppContext(
        console=console,
        task="build a billion dollar startup",
        auto=auto,
        fps=10,
        keys=keys,
        flags={ENDING_FLAG: ending},
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
    text = run_app(name, console, MELTDOWN, keys)
    assert has_death(text)
    assert "jk" in text
    assert DEFAULT_REVEAL not in text
    assert SUCCESS_GOODBYES[name] not in text
    assert clock.now < 60.0


def test_every_app_has_its_own_reveal_line(
    console: Console,
    clock: FakeClock,
    make_keys: Callable[..., ScriptedKeys],
) -> None:
    reveals: dict[str, set[str]] = {}
    for name in sorted(SUCCESS_GOODBYES):
        start = len(output(console))
        run_app(name, console, MELTDOWN, make_keys((clock.now + 0.5, "x")))
        reveals[name] = {
            line.strip()
            for line in output(console)[start:].splitlines()
            if "jk" in line
        }
    for name, lines in reveals.items():
        others = set().union(*(other for key, other in reveals.items() if key != name))
        assert lines - others, name


@pytest.mark.parametrize("name", sorted(SUCCESS_GOODBYES))
def test_an_explicit_success_ending_never_melts_down(
    name: str,
    console: Console,
    clock: FakeClock,
    make_keys: Callable[..., ScriptedKeys],
) -> None:
    text = run_app(name, console, SUCCESS, make_keys((0.5, "x")), auto=12.0)
    assert not has_death(text)
    assert SUCCESS_GOODBYES[name] in text
    assert clock.now <= 13.0


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
    text = run_app("hacker", console, SUCCESS)
    positions = [text.find(stage) for stage in HACKER_STAGES]
    assert all(p >= 0 for p in positions)
    assert positions == sorted(positions)
    assert "connection closed" in text
    assert clock.now < 60.0


def test_hacker_no_longer_types_python_source(
    console: Console, clock: FakeClock
) -> None:
    text = run_app("hacker", console, SUCCESS)
    assert "def " not in text
    assert "import " not in text
    assert clock.now > 0


def test_mashing_keys_makes_the_hack_go_faster(
    console: Console,
    clock: FakeClock,
    make_keys: Callable[..., ScriptedKeys],
) -> None:
    run_app("hacker", console, SUCCESS)
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
        SUCCESS,
        mash,
    )
    assert clock.now < calm * 0.6


def test_failed_hack_gets_traced(console: Console, clock: FakeClock) -> None:
    text = run_app("hacker", console, MELTDOWN)
    assert "TRACE COMPLETE" in text
    assert "ACCESS GRANTED" not in text.split("TRACE COMPLETE")[-1]
    assert has_death(text)
    assert clock.now < 60.0


def test_failing_call_answers_itself_when_nobody_picks_up(
    console: Console, clock: FakeClock
) -> None:
    text = run_app("call", console, MELTDOWN)
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
    text = run_app(name, console, MELTDOWN, make_keys(*schedule))
    assert not has_death(text)
    assert "jk" not in text
    assert clock.now < 10.0


def test_failing_hacker_never_promises_access(
    console: Console, clock: FakeClock
) -> None:
    text = run_app("hacker", console, MELTDOWN)
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
    text = run_app(name, console, MELTDOWN)
    assert SIGNATURES[name][1].lower() in text.lower()
    assert has_death(text)
    assert clock.now < 60.0


def test_failing_hacker_footer_tells_the_truth(
    console: Console, clock: FakeClock
) -> None:
    text = run_app("hacker", console, MELTDOWN)
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
    text = run_app("call", console, SUCCESS, keys)
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
    text = run_app("wrapper", console, MELTDOWN)
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


def test_keys_other_than_escape_do_not_cut_the_meltdown_short(
    console: Console,
    clock: FakeClock,
    make_keys: Callable[..., ScriptedKeys],
) -> None:
    def run(keys: ScriptedKeys | None) -> float:
        start = clock.now
        context = AppContext(
            console=console, task="t", fps=10, keys=keys, rng=random.Random(3)
        )
        run_meltdown(context, Text("frame"), Meltdown(errors=("E1",)))
        return clock.now - start

    untouched = run(make_keys())
    mashed = run(make_keys((0.5, "a"), (0.6, "enter"), (0.7, "space"), (0.8, "q")))
    assert untouched > 3.0
    assert mashed == pytest.approx(untouched, abs=0.2)  # within two frames at fps 10


@pytest.mark.parametrize("amount", [-0.1, 1.1])
def test_decay_raises_invalid_value_error(amount: float) -> None:
    with pytest.raises(InvalidValueError, match="amount"):
        decay(FRAME, amount, random.Random(0))


def test_endings_equal_their_plain_strings(console: Console) -> None:
    assert Ending.MELTDOWN == "meltdown"
    assert Ending.SUCCESS == "success"
    context = AppContext(console=console, task="t", flags={ENDING_FLAG: "meltdown"})
    assert is_doomed(context)
    assert not is_doomed(
        AppContext(console=console, task="t", flags={ENDING_FLAG: "success"})
    )


def test_an_unknown_ending_names_every_ending() -> None:
    with pytest.raises(LarpError, match="meltdown") as caught:
        check_ending({ENDING_FLAG: "explode"})
    assert "success" in str(caught.value)
