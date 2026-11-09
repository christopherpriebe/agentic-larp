import io
import itertools
import random
import re
from collections.abc import Callable, Mapping

import pytest
from rich.console import Console

from agentic_larp.apps import AppContext, app_registry
from agentic_larp.packs import SCENARIOS, pick_scenario
from agentic_larp.questions import Question
from agentic_larp.sim import Sim, SwarmSettings
from agentic_larp.stages import Session, WorkStage
from support import FakeClock, ScriptedKeys, output

DT = 0.05
ANSWER_AT = 1.0
PICK_EVERY = 8.0  # enough for her to finish a node's lines
ENDINGS = {"in a relationship", "ghosted", "merged", "friendzoned"}
STATUS = re.compile(r"relationship status: ([a-z ]+)")
EVERY_PATH = list(itertools.product("123", repeat=3))


def call(
    console: Console,
    keys: ScriptedKeys | None = None,
    flags: Mapping[str, str] | None = None,
    auto: float | None = None,
) -> str:
    app_registry()["call"](
        AppContext(
            console=console,
            task="build me a girlfriend",
            auto=auto,
            fps=4,
            keys=keys,
            rng=random.Random(0),
            flags=dict(flags or {}),
        )
    )
    return output(console)


def fresh_console() -> Console:
    return Console(
        file=io.StringIO(),
        width=140,
        height=44,
        force_terminal=True,
        color_system=None,
        legacy_windows=False,
    )


def walk(
    path: tuple[str, ...],
    clock: FakeClock,
    flags: Mapping[str, str] | None = None,
) -> str:
    clock.now = 0.0  # each call gets its own minute on the fake clock
    picks = ((ANSWER_AT + PICK_EVERY * (i + 1), key) for i, key in enumerate(path))
    keys = ScriptedKeys(clock, [(ANSWER_AT, "x"), *picks])
    return call(fresh_console(), keys, flags)


def statuses(text: str) -> list[str]:
    return [match.group(1) for match in STATUS.finditer(text)]


# ---- the pack -------------------------------------------------------------


def question(key: str) -> Question:
    return next(q for q in SCENARIOS["girlfriend"].questions if q.key == key)


@pytest.mark.parametrize(
    ("key", "flag", "values", "recommended"),
    [
        ("drama", "her.drama", ["none", "some", "max"], "none"),
        ("texting", "her.style", ["soft", "loud", "corporate"], "soft"),
        ("memory", "her.memory", ["ram", "disk"], "ram"),
    ],
)
def test_the_swarm_asks_how_to_build_her(
    key: str, flag: str, values: list[str], recommended: str
) -> None:
    asked = question(key)
    assert asked.when == {}
    assert [option.sets[flag] for option in asked.options] == values
    assert asked.options[asked.recommended].sets[flag] == recommended


def test_the_questions_come_in_build_order() -> None:
    keys = [q.key for q in SCENARIOS["girlfriend"].questions]
    assert keys == ["drama", "jealousy", "texting", "memory"]
    ats = [q.at for q in SCENARIOS["girlfriend"].questions]
    assert ats == sorted(ats)


def test_only_the_jealousy_branch_can_doom_her() -> None:
    jealousy = question("jealousy")
    assert jealousy.when == {"her.drama": "max"}
    assert any(o.sets.get("ending") == "meltdown" for o in jealousy.options)
    recommended = jealousy.options[jealousy.recommended]
    assert "ending" not in recommended.sets
    for asked in SCENARIOS["girlfriend"].questions:
        if asked.key != "jealousy":
            assert all("ending" not in option.sets for option in asked.options)


def start_work(console: Console, clock: FakeClock) -> tuple[Sim, WorkStage]:
    settings = SwarmSettings(agents=4, interns=0, length=10.0)
    sim = Sim([pick_scenario(None, "girlfriend")], settings, random.Random(2))
    session = Session(
        console=console,
        task=sim.task,
        sim=sim,
        rng=random.Random(3),
        keys=ScriptedKeys(clock),
    )
    work = WorkStage()
    work.begin(session)
    return sim, work


def answer_next(sim: Sim, work: WorkStage, key: str) -> str:
    for _ in range(int(12.0 / DT)):
        if sim.open_question is not None:
            break
        work.tick(DT)
    asked = sim.open_question
    assert asked is not None
    for _ in range(int(1.0 / DT)):  # past the grace period
        work.tick(DT)
    work.on_key(key)
    return asked[1].key


@pytest.mark.parametrize(
    ("drama_key", "expected"),
    [
        ("1", ["drama", "texting", "memory"]),
        ("3", ["drama", "jealousy", "texting", "memory"]),
    ],
)
def test_jealousy_is_asked_only_after_maximum_drama(
    console: Console, clock: FakeClock, drama_key: str, expected: list[str]
) -> None:
    sim, work = start_work(console, clock)
    asked = [answer_next(sim, work, drama_key)]
    asked += [answer_next(sim, work, "2") for _ in expected[1:]]
    assert asked == expected


@pytest.mark.parametrize(
    ("task", "key"),
    [
        ("build me a girlfriend", "girlfriend"),
        ("build me a gf", "girlfriend"),
        ("I'm so single", "girlfriend"),
        ("build me a boyfriend", "generic"),
        ("build me a husband", "generic"),
        ("i want a wife", "generic"),
    ],
)
def test_she_answers_only_to_girlfriend_words(task: str, key: str) -> None:
    assert pick_scenario(task, rng=random.Random(0)).key == key


# ---- the dialogue tree ----------------------------------------------------


def test_picking_replies_reaches_an_ending(
    clock: FakeClock,
) -> None:
    text = walk(("1", "1", "1"), clock)
    assert statuses(text) == ["in a relationship"]
    assert clock.now < 60.0


def test_every_ending_is_reachable(clock: FakeClock) -> None:
    reached = set()
    for path in EVERY_PATH:
        found = statuses(walk(path, clock))
        assert len(found) == 1, path
        reached.add(found[0])
    assert reached == ENDINGS


def test_a_digit_after_text_is_typed_not_picked(
    console: Console, make_keys: Callable[..., ScriptedKeys]
) -> None:
    keys = make_keys(
        (ANSWER_AT, "x"),
        *((9.0, key) for key in "zz1"),
        (9.0, "enter"),
        (12.0, "esc"),
    )
    text = call(console, keys)
    assert "zz1" in text
    assert statuses(text) == []
    assert "says goodnight" in text


def test_a_digit_past_the_replies_does_nothing(
    console: Console, make_keys: Callable[..., ScriptedKeys]
) -> None:
    keys = make_keys(
        (ANSWER_AT, "x"), (9.0, "4"), (10.0, "9"), (11.0, "0"), (14.0, "esc")
    )
    text = call(console, keys)
    assert statuses(text) == []
    assert "says goodnight" in text


def test_hanging_up_still_says_goodnight(
    console: Console, make_keys: Callable[..., ScriptedKeys]
) -> None:
    text = call(console, make_keys((ANSWER_AT, "x"), (9.0, "1"), (12.0, "esc")))
    assert "says goodnight" in text
    assert statuses(text) == []


def test_demo_mode_answers_and_talks_by_itself(
    console: Console, clock: FakeClock
) -> None:
    text = call(console, auto=45.0)
    assert statuses(text) == ["in a relationship"]
    assert clock.now <= 46.0


@pytest.mark.usefixtures("clock")
def test_demo_mode_cut_short_just_says_goodnight(console: Console) -> None:
    text = call(console, auto=8.0)
    assert statuses(text) == []
    assert "says goodnight" in text


def test_a_digit_pressed_while_she_types_is_dropped(clock: FakeClock) -> None:
    clock.now = 0.0
    picks = [(ANSWER_AT + PICK_EVERY * (i + 1), "1") for i in range(3)]
    keys = ScriptedKeys(clock, [(ANSWER_AT, "x"), (2.0, "1"), *picks])
    text = call(fresh_console(), keys)
    assert statuses(text) == ["in a relationship"]


def test_hanging_up_during_an_ending_keeps_the_ending(clock: FakeClock) -> None:
    clock.now = 0.0
    picks = [(ANSWER_AT + PICK_EVERY * (i + 1), "1") for i in range(3)]
    last = picks[-1][0]
    keys = ScriptedKeys(clock, [(ANSWER_AT, "x"), *picks, (last + 0.5, "esc")])
    text = call(fresh_console(), keys)
    assert statuses(text) == ["in a relationship"]
    assert "says goodnight" not in text


def test_a_failing_call_offers_no_replies(
    console: Console, make_keys: Callable[..., ScriptedKeys]
) -> None:
    keys = make_keys(
        (ANSWER_AT, "x"), *((ANSWER_AT + 0.5 * i, "1") for i in range(4, 20))
    )
    text = call(console, keys, {"ending": "meltdown"})
    assert "jk" in text
    assert "hey you" not in text
    assert "zero warnings?" not in text  # a reply row
    assert statuses(text) == []


# ---- the flags shape her --------------------------------------------------


@pytest.mark.parametrize(
    ("flags", "present", "absent"),
    [
        ({}, ["it's me"], ["IT'S ME", "per my last text"]),
        ({"her.style": "soft"}, ["it's me"], ["IT'S ME", "per my last text"]),
        ({"her.style": "loud"}, ["IT'S ME", "!!"], ["it's me"]),
        ({"her.style": "corporate"}, ["per my last text"], ["IT'S ME"]),
        ({"her.style": "sarcastic"}, ["it's me"], ["IT'S ME", "per my last text"]),
    ],
)
def test_her_texting_style_follows_the_swarm(
    console: Console,
    make_keys: Callable[..., ScriptedKeys],
    flags: dict[str, str],
    present: list[str],
    absent: list[str],
) -> None:
    text = call(console, make_keys((ANSWER_AT, "x"), (12.0, "esc")), flags)
    for phrase in present:
        assert phrase in text
    for phrase in absent:
        assert phrase not in text


@pytest.mark.parametrize(
    ("flags", "mood"),
    [
        ({}, "calm"),
        ({"her.drama": "none"}, "calm"),
        ({"her.drama": "some"}, "calm"),
        ({"her.drama": "max"}, "jealous"),
    ],
)
def test_maximum_drama_opens_the_jealous_branch(
    clock: FakeClock,
    flags: dict[str, str],
    mood: str,
) -> None:
    texts = [walk(path, clock, flags) for path in EVERY_PATH]
    assert any("other tabs" in text for text in texts) is (mood == "jealous")
    assert all(len(statuses(text)) == 1 for text in texts)


@pytest.mark.parametrize(
    ("flags", "present", "absent"),
    [
        ({}, "lives in RAM", "birthdays.db"),
        ({"her.memory": "ram"}, "lives in RAM", "saved to birthdays.db"),
        ({"her.memory": "disk"}, "saved to birthdays.db", "lives in RAM"),
    ],
)
def test_persisting_her_changes_the_goodbye(
    console: Console,
    make_keys: Callable[..., ScriptedKeys],
    flags: dict[str, str],
    present: str,
    absent: str,
) -> None:
    text = call(console, make_keys((ANSWER_AT, "x"), (12.0, "esc")), flags)
    goodbye = text.rsplit("\x1b[?1049l", 1)[-1]  # after the full-screen call
    assert present in goodbye
    assert absent not in goodbye
