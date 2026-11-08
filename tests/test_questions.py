import math
import random
from collections.abc import Callable
from pathlib import Path

import pytest
from rich.console import Console

from agentic_larp import GrammarError, LarpError, main
from agentic_larp.events import QuestionAnswered, QuestionAsked
from agentic_larp.packs import SCENARIOS, Scenario, load_scenario, pick_scenario
from agentic_larp.questions import Option, Question
from agentic_larp.sim import RunMode, Sim, SwarmSettings
from agentic_larp.stages import Session, WorkStage
from support import FakeClock, ScriptedKeys

DT = 0.05
YES = Option("Yes, ship it", "what could go wrong", sets={"ending": "meltdown"})
NO = Option("Wait until Monday", sets={"ending": "success"})


def friday(*, at: float = 0.1, key: str = "friday") -> Question:
    return Question(key, "Deploy to prod on a Friday?", (YES, NO), recommended=0, at=at)


def with_questions(*questions: Question) -> Scenario:
    base = pick_scenario(None, "prod")
    return Scenario(
        key="asking",
        task=base.task,
        keywords=(),
        areas=base.areas,
        app="none",
        grammar=base.grammar,
        questions=questions,
    )


def make_sim(
    *questions: Question,
    length: float = 10.0,
    agents: int = 3,
    mode: RunMode = RunMode.CONVERGE,
) -> Sim:
    settings = SwarmSettings(agents=agents, interns=0, length=length, mode=mode)
    return Sim([with_questions(*questions)], settings, random.Random(2))


def run(sim: Sim, seconds: float) -> None:
    for _ in range(int(seconds / DT)):
        sim.tick(DT)


# ---- the data model -------------------------------------------------------


@pytest.mark.parametrize(
    ("make", "message"),
    [
        pytest.param(lambda: Question("q", "?", (YES,)), "option", id="one-option"),
        pytest.param(lambda: Question("q", "?", (YES, NO) * 3), "option", id="six"),
        pytest.param(
            lambda: Question("q", "?", (YES, NO), recommended=2),
            "recommended",
            id="rec-high",
        ),
        pytest.param(
            lambda: Question("q", "?", (YES, NO), recommended=-1),
            "recommended",
            id="rec-low",
        ),
        pytest.param(lambda: Question("q", "?", (YES, NO), at=1.5), "at", id="at-high"),
        pytest.param(
            lambda: Question("q", "?", (YES, NO), at=math.nan), "at", id="at-nan"
        ),
        pytest.param(lambda: Question("q", "?", (YES, YES)), "label", id="duplicate"),
        pytest.param(lambda: Question(" ", "?", (YES, NO)), "key", id="blank-key"),
        pytest.param(
            lambda: Question("q", " ", (YES, NO)), "prompt", id="blank-prompt"
        ),
        pytest.param(lambda: Option(" "), "label", id="blank-label"),
        pytest.param(lambda: Option("x", todos=6), "todos", id="todos-high"),
        pytest.param(lambda: Option("x", todos=-1), "todos", id="todos-low"),
        pytest.param(lambda: Option("x", spawn=4), "spawn", id="spawn-high"),
        pytest.param(
            lambda: Option("x", sets={"ending": "kaboom"}), "'kaboom'", id="ending"
        ),
    ],
)
def test_questions_reject_bad_settings(
    make: Callable[[], object], message: str
) -> None:
    with pytest.raises(LarpError, match=message):
        make()


def test_question_defaults() -> None:
    question = Question("q", "Ship it?", (YES, NO))
    assert question.recommended == 0
    assert 0.0 <= question.at <= 1.0
    assert dict(question.when) == {}
    assert Option("Sure").description == ""
    assert (Option("Sure").todos, Option("Sure").spawn) == (0, 0)


# ---- packs ----------------------------------------------------------------

PARENT = """
[pack]
key = "parent"
task = "t"
[areas]
core = ["core.py"]

[[questions]]
key = "q"
prompt = "Parent asks?"
at = 0.2
[[questions.options]]
label = "A"
[[questions.options]]
label = "B"
sets = { ending = "meltdown" }

[[questions]]
key = "p"
prompt = "Second?"
recommended = 1
when = { ending = "meltdown" }
[[questions.options]]
label = "C"
todos = 2
[[questions.options]]
label = "D"
spawn = 1
"""


def write(directory: Path, name: str, text: str) -> Path:
    path = directory / f"{name}.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_packs_declare_questions(tmp_path: Path) -> None:
    pack = load_scenario(write(tmp_path, "parent", PARENT))
    first, second = pack.questions
    assert (first.key, first.prompt, first.at) == ("q", "Parent asks?", 0.2)
    assert [option.label for option in first.options] == ["A", "B"]
    assert dict(first.options[1].sets) == {"ending": "meltdown"}
    assert second.recommended == 1
    assert dict(second.when) == {"ending": "meltdown"}
    assert (second.options[0].todos, second.options[1].spawn) == (2, 1)


def test_a_child_pack_overrides_questions_by_key(tmp_path: Path) -> None:
    parent = load_scenario(write(tmp_path, "parent", PARENT))
    child_text = """
[pack]
key = "child"
extends = "parent"

[[questions]]
key = "q"
prompt = "Child asks?"
[[questions.options]]
label = "Yes"
[[questions.options]]
label = "No"

[[questions]]
key = "r"
prompt = "New one?"
[[questions.options]]
label = "Yes"
[[questions.options]]
label = "No"
"""
    child = load_scenario(
        write(tmp_path, "child", child_text), packs={"parent": parent}
    )
    assert [q.key for q in child.questions] == ["q", "p", "r"]
    assert child.questions[0].prompt == "Child asks?"


@pytest.mark.parametrize(
    "body",
    [
        '[[questions]]\nkey = "q"\nprompt = "?"\n',
        '[[questions]]\nkey = "q"\nprompt = "?"\noptions = "nope"\n',
        '[[questions]]\nprompt = "?"\n[[questions.options]]\nlabel = "a"\n[[questions.options]]\nlabel = "b"\n',
        '[[questions]]\nkey = "q"\nprompt = "?"\nat = 3\n[[questions.options]]\nlabel = "a"\n[[questions.options]]\nlabel = "b"\n',
    ],
    ids=["no-options", "options-not-a-table", "no-key", "bad-at"],
)
def test_a_malformed_question_names_the_pack(tmp_path: Path, body: str) -> None:
    text = '[pack]\nkey = "broken"\ntask = "t"\n[areas]\nx = ["x.py"]\n' + body
    with pytest.raises(GrammarError, match=r"broken\.toml"):
        load_scenario(write(tmp_path, "broken", text))


def test_prod_asks_about_friday_deploys() -> None:
    question = next(q for q in SCENARIOS["prod"].questions if q.key == "friday")
    recommended = question.options[question.recommended]
    assert dict(recommended.sets) == {"ending": "meltdown"}
    assert "(" not in recommended.label  # the screen adds "(Recommended)"


# ---- the sim --------------------------------------------------------------


def test_asking_pauses_only_the_asking_agent() -> None:
    sim = make_sim(length=30.0)
    run(sim, 1.0)
    asker, other = sim.agents[0], sim.agents[1]
    sim.ask(asker, friday())
    before = (asker.calls, asker.todos_done, len(asker.log), asker.tokens)
    other_calls = other.calls
    run(sim, 5.0)
    assert (asker.calls, asker.todos_done, len(asker.log), asker.tokens) == before
    assert other.calls > other_calls
    assert sim.open_question == (asker, friday())


def test_answering_resumes_and_applies_the_option() -> None:
    sim = make_sim(length=30.0)
    asked: list[QuestionAsked] = []
    answered: list[QuestionAnswered] = []
    sim.events.subscribe(QuestionAsked, asked.append)
    sim.events.subscribe(QuestionAnswered, answered.append)
    asker = sim.agents[0]
    question = Question("q", "More?", (Option("More", todos=2, spawn=1), NO))
    todos, agents = len(asker.todos), len(sim.agents)
    sim.ask(asker, question)
    option = sim.answer(0)
    assert option is question.options[0]
    assert sim.open_question is None
    assert len(asker.todos) == todos + 2
    assert len(sim.agents) == agents + 1
    assert asked == [QuestionAsked(asker, question)]
    assert answered == [QuestionAnswered(asker, question, option)]
    calls = asker.calls
    run(sim, 3.0)
    assert asker.calls > calls


def test_answering_without_a_question_or_out_of_range_is_an_error() -> None:
    sim = make_sim()
    with pytest.raises(LarpError, match="no question"):
        sim.answer(0)
    sim.ask(sim.agents[0], friday())
    with pytest.raises(LarpError, match="option"):
        sim.answer(2)
    with pytest.raises(LarpError, match="already"):
        sim.ask(sim.agents[1], friday(key="other"))


def test_a_swarm_still_converges_after_a_question() -> None:
    sim = make_sim(length=5.0)
    run(sim, 1.0)
    sim.ask(sim.agents[0], friday())
    run(sim, 3.0)
    sim.answer(1)
    run(sim, 12.0)
    assert sim.is_converged


# ---- the work stage -------------------------------------------------------


def start_work(
    console: Console, clock: FakeClock, sim: Sim, *, auto: float | None = None
) -> tuple[Session, WorkStage]:
    session = Session(
        console=console,
        task=sim.task,
        sim=sim,
        rng=random.Random(3),
        keys=ScriptedKeys(clock),
        auto=auto,
    )
    work = WorkStage()
    work.begin(session)
    return session, work


def advance(work: WorkStage, seconds: float) -> None:
    for _ in range(int(seconds / DT)):
        if work.is_done:
            return
        work.tick(DT)


def screen(console: Console, work: WorkStage) -> str:
    with console.capture() as capture:
        console.print(work.render(), height=console.height)
    return capture.get()


def test_a_question_is_asked_once_its_time_comes(
    console: Console, clock: FakeClock
) -> None:
    sim = make_sim(friday(at=0.3), length=10.0)
    _, work = start_work(console, clock, sim)
    advance(work, 2.5)
    assert sim.open_question is None
    advance(work, 1.0)
    assert sim.open_question is not None
    text = screen(console, work)
    assert "Deploy to prod on a Friday?" in text
    assert "1. Yes, ship it (Recommended)" in text
    assert "2. Wait until Monday" in text
    assert "what could go wrong" in text
    assert "\u276f" in text  # the cursor


def test_a_number_key_answers_and_sets_the_flags(
    console: Console, clock: FakeClock
) -> None:
    sim = make_sim(friday(), length=10.0)
    session, work = start_work(console, clock, sim)
    advance(work, 2.0)  # past the 0.5 s grace period
    work.on_key("2")
    assert sim.open_question is None
    assert session.flags["ending"] == "success"
    assert "Deploy to prod on a Friday?" not in screen(console, work)
    advance(work, 30.0)
    assert sim.open_question is None  # asked once only


def test_arrows_and_enter_pick_an_option(console: Console, clock: FakeClock) -> None:
    sim = make_sim(friday(), length=10.0)
    session, work = start_work(console, clock, sim)
    advance(work, 2.0)  # past the 0.5 s grace period
    work.on_key("down")
    work.on_key("down")  # stays on the last option
    work.on_key("up")
    work.on_key("down")
    work.on_key("enter")
    assert session.flags["ending"] == "success"


def test_escape_picks_the_recommended_option(
    console: Console, clock: FakeClock
) -> None:
    sim = make_sim(friday(), length=10.0)
    session, work = start_work(console, clock, sim)
    advance(work, 2.0)  # past the 0.5 s grace period
    work.on_key("down")
    work.on_key("esc")
    assert session.flags["ending"] == "meltdown"
    assert not work.is_done


def test_typing_is_ignored_while_a_question_is_open(
    console: Console, clock: FakeClock
) -> None:
    sim = make_sim(friday(), length=10.0)
    session, work = start_work(console, clock, sim)
    advance(work, 2.0)  # past the 0.5 s grace period
    for key in "ship it":
        work.on_key(key)
    work.on_key("x")
    assert session.wall is not None
    assert session.wall.buffer == ""
    assert sim.open_question is not None
    assert not work.is_done


def test_answers_branch_into_follow_up_questions(
    console: Console, clock: FakeClock
) -> None:
    follow_up = Question(
        "rollback",
        "Prod is down. Roll back?",
        (Option("Roll forward"), Option("Roll back")),
        at=0.1,
        when={"ending": "meltdown"},
    )
    calm = Question(
        "coffee",
        "Coffee?",
        (Option("Yes"), Option("No")),
        at=0.1,
        when={"ending": "success"},
    )
    sim = make_sim(friday(), follow_up, calm, length=10.0)
    _, work = start_work(console, clock, sim)
    advance(work, 2.0)  # past the 0.5 s grace period
    work.on_key("1")  # meltdown
    advance(work, 1.0)
    assert sim.open_question is not None
    assert sim.open_question[1].key == "rollback"
    work.on_key("1")
    advance(work, 20.0)
    assert sim.open_question is None


def test_one_question_at_a_time(console: Console, clock: FakeClock) -> None:
    first, second = friday(key="first"), friday(key="second")
    sim = make_sim(first, second, length=10.0)
    _, work = start_work(console, clock, sim)
    advance(work, 3.0)
    assert sim.open_question is not None
    assert sim.open_question[1].key == "first"
    work.on_key("1")
    advance(work, 0.2)
    assert sim.open_question is not None
    assert sim.open_question[1].key == "second"


def test_demo_mode_takes_the_recommendation_and_waits_to_ship(
    console: Console, clock: FakeClock
) -> None:
    sim = make_sim(friday(at=0.05), length=10.0)
    session, work = start_work(console, clock, sim, auto=1.0)
    answered: list[float] = []
    sim.events.subscribe(QuestionAnswered, lambda _event: answered.append(sim.now))
    advance(work, 2.5)
    assert sim.open_question is not None
    assert not work.is_done  # auto-ship waits while a question is open
    advance(work, 2.0)
    assert answered
    assert 2.9 <= answered[0] <= 3.2
    assert session.flags["ending"] == "meltdown"
    assert work.is_done


def test_endless_runs_ask_too(console: Console, clock: FakeClock) -> None:
    sim = make_sim(friday(), length=10.0, mode=RunMode.ENDLESS)
    _, work = start_work(console, clock, sim)
    advance(work, 2.0)  # past the 0.5 s grace period
    assert sim.open_question is not None


def test_a_recommended_meltdown_reaches_the_app(
    capsys: pytest.CaptureFixture[str], clock: FakeClock
) -> None:
    assert main(["-s", "prod", "--auto", "8", "--speed", "4", "-i", "0"]) == 0
    text = capsys.readouterr().out
    assert "jk" in text
    assert "✓ shipped" in text
    assert clock.now > 8.0


# ---- review round -----------------------------------------------------------


def test_keys_typed_just_as_a_question_opens_do_not_answer_it(
    console: Console, clock: FakeClock
) -> None:
    sim = make_sim(friday(at=0.3), length=10.0)
    session, work = start_work(console, clock, sim)
    advance(work, 2.9)
    for key in "deploy ":
        work.on_key(key)
    advance(work, 0.2)  # the question opens now
    assert sim.open_question is not None
    work.on_key("2")
    work.on_key("enter")
    assert sim.open_question is not None  # too soon: ignored
    assert "ending" not in session.flags
    advance(work, 0.6)
    work.on_key("2")
    assert session.flags["ending"] == "success"
    assert session.wall is not None
    assert session.wall.buffer == "deploy "  # handed back after the answer


def test_a_second_escape_right_after_answering_does_not_quit(
    console: Console, clock: FakeClock
) -> None:
    sim = make_sim(friday(), length=10.0)
    _, work = start_work(console, clock, sim)
    advance(work, 2.0)
    work.on_key("esc")
    work.on_key("esc")
    assert not work.is_done
    assert work.next_stage is None


def test_shipping_answers_an_open_question_with_its_recommendation(
    console: Console, clock: FakeClock
) -> None:
    sim = make_sim(length=30.0)
    session, _work = start_work(console, clock, sim)
    sim.ask(sim.agents[0], friday())
    sim.ship()
    assert sim.open_question is None
    assert session.flags["ending"] == "meltdown"
    run(sim, 6.0)
    assert sim.is_all_done


def test_no_question_is_asked_once_shipping_started() -> None:
    sim = make_sim()
    sim.ship()
    with pytest.raises(LarpError, match="shipping"):
        sim.ask(sim.agents[0], friday())


def test_the_asking_agent_shows_it_is_waiting(
    console: Console, clock: FakeClock
) -> None:
    sim = make_sim(friday(), length=10.0, agents=2)
    _, work = start_work(console, clock, sim)
    advance(work, 1.5)
    assert sim.open_question is not None
    asker = sim.open_question[0]
    lines = screen(console, work).splitlines()
    assert any(
        asker.name in line and "waiting for you" in line.lower() for line in lines
    )
    footer = lines[-1]
    assert "esc to quit" not in footer
    assert "Message" not in footer


def test_a_flag_you_pinned_is_never_overridden_by_a_question(
    capsys: pytest.CaptureFixture[str], clock: FakeClock
) -> None:
    args = ["-s", "prod", "--auto", "8", "--speed", "4", "-i", "0"]
    assert main([*args, "--flag", "ending=success"]) == 0
    text = capsys.readouterr().out
    assert "jk" not in text
    assert "✓ shipped" in text
    assert clock.now > 8.0


def test_the_question_fits_a_small_terminal(clock: FakeClock) -> None:
    small = Console(width=80, height=20, force_terminal=True, color_system=None)
    long = Question(
        "q",
        "Deploy to prod on a Friday? " * 3,
        tuple(Option(f"Option {n}", "a long description " * 4) for n in range(4)),
    )
    sim = make_sim(long, length=10.0, agents=2)
    _, work = start_work(small, clock, sim)
    advance(work, 6.0)
    assert sim.open_question is not None
    with small.capture() as capture:
        small.print(work.render(), height=20)
    text = capture.get()
    assert len(text.splitlines()) <= 20
    for n in range(1, 5):
        assert f"{n}. Option {n - 1}" in text


def test_questions_from_two_packs_with_one_key_ask_once(
    console: Console, clock: FakeClock
) -> None:
    settings = SwarmSettings(agents=2, interns=0, length=10.0)
    packs = [with_questions(friday()), with_questions(friday())]
    sim = Sim(packs, settings, random.Random(2))
    _, work = start_work(console, clock, sim)
    advance(work, 1.5)
    work.on_key("1")
    advance(work, 20.0)
    assert sim.open_question is None


def test_with_two_parents_the_later_question_wins_in_the_first_place(
    tmp_path: Path,
) -> None:
    first = load_scenario(write(tmp_path, "parent", PARENT))
    second_text = PARENT.replace('key = "parent"', 'key = "other"').replace(
        "Parent asks?", "Other asks?"
    )
    second = load_scenario(write(tmp_path, "other", second_text))
    child = load_scenario(
        write(
            tmp_path, "child", '[pack]\nkey = "child"\nextends = ["parent", "other"]\n'
        ),
        packs={"parent": first, "other": second},
    )
    assert [q.key for q in child.questions] == ["q", "p"]
    assert child.questions[0].prompt == "Other asks?"


OPTIONS = '[[questions.options]]\nlabel = "a"\n[[questions.options]]\nlabel = "b"\n'


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ('questions = "nope"\n', "questions"),
        ("questions = [1]\n", "question"),
        ('[[questions]]\nkey = "q"\n' + OPTIONS, "prompt"),
        ('[[questions]]\nkey = "q"\nprompt = "?"\nat = "soon"\n' + OPTIONS, "at"),
        ('[[questions]]\nkey = "q"\nprompt = "?"\nwhen = "x"\n' + OPTIONS, "when"),
        ('[[questions]]\nkey = "q"\nprompt = "?"\noptions = [1, 2]\n', "option"),
        (
            '[[questions]]\nkey = "q"\nprompt = "?"\n[[questions.options]]\nlabel = 3\n[[questions.options]]\nlabel = "b"\n',
            "label",
        ),
        (
            '[[questions]]\nkey = "q"\nprompt = "?"\n[[questions.options]]\nlabel = "a"\nsets = 1\n[[questions.options]]\nlabel = "b"\n',
            "sets",
        ),
        (
            '[[questions]]\nkey = "q"\nprompt = "?"\n[[questions.options]]\nlabel = "a"\ntodos = 1.5\n[[questions.options]]\nlabel = "b"\n',
            "todos",
        ),
        (
            '[[questions]]\nkey = "q"\nprompt = "?"\n[[questions.options]]\nlabel = "a"\ntodos = 9\n[[questions.options]]\nlabel = "b"\n',
            "'q'",
        ),
    ],
    ids=[
        "not-an-array",
        "not-a-table",
        "no-prompt",
        "at-text",
        "when-text",
        "option-not-a-table",
        "label-number",
        "sets-number",
        "todos-float",
        "names-question",
    ],
)
def test_malformed_questions_explain_themselves(
    tmp_path: Path, body: str, message: str
) -> None:
    text = '[pack]\nkey = "broken"\ntask = "t"\n[areas]\nx = ["x.py"]\n' + body
    with pytest.raises(GrammarError, match=message):
        load_scenario(write(tmp_path, "broken", text))


def test_question_options_are_kept_as_a_tuple() -> None:
    options = [YES, NO]
    question = Question("friday", "Ship?", options)  # ty: ignore[invalid-argument-type] - a list is what a careless caller passes
    options.append(NO)
    assert question.options == (YES, NO)
