import random
from collections.abc import Callable

import pytest
from rich.console import Console

from agentic_larp import LarpError
from agentic_larp.events import (
    AgentFinished,
    AgentSpawned,
    Converged,
    Event,
    EventBus,
    LineShown,
    Report,
    ScopeCreep,
    ShipStarted,
    TodoDone,
)
from agentic_larp.packs import SCENARIOS, pick_scenario
from agentic_larp.sim import AgentView, LogLine, RunMode, Sim, SwarmSettings
from agentic_larp.stages import Session, run_flow
from support import FakeClock, ScriptedKeys

DT = 0.05


def make_sim(
    *,
    length: float = 10.0,
    mode: RunMode = RunMode.CONVERGE,
    agents: int = 4,
    key: str = "prod",
    log_length: int | None = 120,
) -> Sim:
    settings = SwarmSettings(
        agents=agents, interns=0, length=length, mode=mode, log_length=log_length
    )
    return Sim([pick_scenario(None, key)], settings, random.Random(5))


def run(sim: Sim, seconds: float) -> None:
    for _ in range(int(seconds / DT)):
        sim.tick(DT)


def test_handlers_get_events_in_order_by_subscription() -> None:
    bus = EventBus()
    seen: list[tuple[str, str]] = []
    bus.subscribe(Report, lambda event: seen.append(("first", event.text)))
    bus.subscribe(Report, lambda event: seen.append(("second", event.text)))
    bus.publish(Report("you", "a"))
    bus.publish(Report("you", "b"))
    assert seen == [("first", "a"), ("second", "a"), ("first", "b"), ("second", "b")]


def test_subscribing_to_the_base_class_gets_everything() -> None:
    bus = EventBus()
    everything: list[Event] = []
    reports: list[Report] = []
    bus.subscribe(Event, everything.append)
    bus.subscribe(Report, reports.append)
    bus.publish(ShipStarted())
    bus.publish(Report("x", "y"))
    assert everything == [ShipStarted(), Report("x", "y")]
    assert reports == [Report("x", "y")]


def test_unsubscribe_stops_delivery() -> None:
    bus = EventBus()
    seen: list[Event] = []
    unsubscribe = bus.subscribe(Event, seen.append)
    bus.publish(ShipStarted())
    unsubscribe()
    bus.publish(ShipStarted())
    assert seen == [ShipStarted()]


def test_unsubscribing_twice_leaves_a_duplicate_subscription_alone() -> None:
    bus = EventBus()
    seen: list[Event] = []
    first = bus.subscribe(Event, seen.append)
    bus.subscribe(Event, seen.append)
    first()
    first()
    bus.publish(ShipStarted())
    assert seen == [ShipStarted()]


def test_agent_events_are_hashable_by_identity() -> None:
    sim = make_sim()
    first, second = sim.agents[0], sim.agents[1]
    assert {AgentSpawned(first), AgentSpawned(first), AgentSpawned(second)} == {
        AgentSpawned(first),
        AgentSpawned(second),
    }
    assert AgentSpawned(first) != AgentSpawned(second)


def test_a_failing_handler_propagates() -> None:
    bus = EventBus()

    def explode(_event: Event) -> None:
        message = "handler broke"
        raise RuntimeError(message)

    bus.subscribe(Event, explode)
    with pytest.raises(RuntimeError, match="handler broke"):
        bus.publish(ShipStarted())


def test_publishing_with_no_subscribers_is_fine() -> None:
    EventBus().publish(Converged())


def test_spawning_publishes_agent_spawned() -> None:
    sim = make_sim()
    spawned: list[AgentSpawned] = []
    sim.events.subscribe(AgentSpawned, spawned.append)
    agent = sim.spawn_agent()
    assert spawned == [AgentSpawned(agent)]


def test_every_line_that_reaches_a_panel_is_published_in_order() -> None:
    sim = make_sim(length=5.0, log_length=None)  # uncapped, to compare everything
    start = {agent.name: len(agent.log) for agent in sim.agents}
    shown: dict[str, list[LogLine]] = {agent.name: [] for agent in sim.agents}
    sim.events.subscribe(
        LineShown, lambda event: shown[event.agent.name].append(event.line)
    )
    run(sim, 10.0)
    assert sim.is_all_done
    for agent in sim.agents:
        assert shown[agent.name] == list(agent.log)[start[agent.name] :]
        assert shown[agent.name]


def test_todo_done_fires_once_per_completed_todo() -> None:
    sim = make_sim(length=5.0)
    done: list[TodoDone] = []
    sim.events.subscribe(TodoDone, done.append)
    run(sim, 10.0)
    for agent in sim.agents:
        mine = [event.todo for event in done if event.agent is agent]
        assert mine == agent.todos


def test_endless_runs_publish_scope_creep_with_the_new_todos() -> None:
    sim = make_sim(length=3.0, mode=RunMode.ENDLESS)
    creep: list[ScopeCreep] = []
    sim.events.subscribe(ScopeCreep, creep.append)
    run(sim, 20.0)
    assert creep
    for event in creep:
        assert event.added
        assert all(todo in event.agent.todos for todo in event.added)


def test_converged_comes_once_after_every_agent_finished() -> None:
    sim = make_sim(length=5.0)
    order: list[Event] = []
    sim.events.subscribe(Event, order.append)
    run(sim, 12.0)
    kinds = [type(event) for event in order]
    assert kinds.count(Converged) == 1
    finished = [i for i, kind in enumerate(kinds) if kind is AgentFinished]
    assert len(finished) == len(sim.agents)
    assert max(finished) < kinds.index(Converged)
    names = {event.agent.name for event in order if isinstance(event, AgentFinished)}
    assert names == {agent.name for agent in sim.agents}


def test_ship_started_fires_once() -> None:
    sim = make_sim(length=60.0)
    started: list[ShipStarted] = []
    sim.events.subscribe(ShipStarted, started.append)
    sim.ship()
    sim.ship()
    run(sim, 6.0)
    assert started == [ShipStarted()]


def test_a_rushed_swarm_never_converges() -> None:
    sim = make_sim(length=60.0)
    converged: list[Converged] = []
    sim.events.subscribe(Converged, converged.append)
    sim.ship()
    run(sim, 6.0)
    assert sim.is_all_done
    assert converged == []


def test_shipping_at_the_last_moment_is_still_a_rush() -> None:
    sim = make_sim(length=5.0)
    events: list[Event] = []
    sim.events.subscribe(Event, events.append)
    while not any(agent.is_done for agent in sim.agents):
        sim.tick(DT)
    sim.ship()
    run(sim, 8.0)
    assert sim.is_all_done
    assert not any(isinstance(event, Converged) for event in events)


def test_a_finished_agent_is_done_when_its_events_arrive() -> None:
    sim = make_sim(length=5.0)
    states: list[bool] = []

    def on_finished(event: AgentFinished) -> None:
        states.append(event.agent.is_done)

    def on_line(event: LineShown) -> None:
        if event.line.kind == "done":
            states.append(event.agent.is_done)

    sim.events.subscribe(AgentFinished, on_finished)
    sim.events.subscribe(LineShown, on_line)
    run(sim, 10.0)
    assert len(states) == 2 * len(sim.agents)
    assert all(states)


def test_report_publishes_and_is_kept() -> None:
    sim = make_sim()
    reports: list[Report] = []
    sim.events.subscribe(Report, reports.append)
    sim.report("you", "hello")
    assert reports == [Report("you", "hello")]
    assert sim.reports[-1] == ("you", "hello")
    for index in range(20):
        sim.report("x", str(index))
    assert len(sim.reports) == 12


def test_stage_messages_arrive_as_reports(console: Console, clock: FakeClock) -> None:
    sim = make_sim(key="startup", length=5.0)
    reports: list[Report] = []
    sim.events.subscribe(Report, reports.append)
    burst = [(3.0, key) for key in [*"hi there", "enter"]]
    keys = ScriptedKeys(clock, [*burst, (30.0, "enter")])
    session = Session(
        console=console, task=sim.task, sim=sim, rng=random.Random(1), keys=keys
    )
    assert run_flow(session) == 0
    texts = [(event.who, event.text) for event in reports]
    assert ("you", "hi there") in texts
    assert (sim.orchestrator, "all 4 agents done. ready to ship.") in texts


def test_ship_started_fires_when_a_converged_run_ships(
    console: Console, clock: FakeClock
) -> None:
    sim = make_sim(key="startup", length=3.0)
    started: list[ShipStarted] = []
    sim.events.subscribe(ShipStarted, started.append)
    keys = ScriptedKeys(clock, [*((20.0, key) for key in "ship it"), (20.0, "enter")])
    session = Session(
        console=console, task=sim.task, sim=sim, rng=random.Random(1), keys=keys
    )
    assert run_flow(session) == 0
    assert sim.is_converged
    assert started == [ShipStarted()]


def test_a_handler_unsubscribed_mid_publish_still_gets_that_event() -> None:
    bus = EventBus()
    received: list[str] = []
    cancels: dict[str, Callable[[], None]] = {}

    def first(_event: Converged) -> None:
        received.append("first")
        cancels["second"]()

    bus.subscribe(Converged, first)
    cancels["second"] = bus.subscribe(Converged, lambda _e: received.append("second"))
    bus.publish(Converged())
    assert received == ["first", "second"]
    bus.publish(Converged())
    assert received == ["first", "second", "first"]


STABLE_AGENT_FIELDS = {
    "name",
    "area",
    "files",
    "is_done",
    "verb",
    "finish_at",
    "tokens",
    "calls",
    "todos_done",
    "todos",
    "log",
    "last_active",
    "scenario_key",
}


def test_agent_view_names_exactly_the_stable_fields() -> None:
    members = {name for name in dir(AgentView) if not name.startswith("_")}
    assert members == STABLE_AGENT_FIELDS


def test_events_carry_the_live_agent_as_an_agent_view() -> None:
    sim = make_sim(length=2.0)
    seen: list[object] = []
    sim.events.subscribe(AgentSpawned, lambda event: seen.append(event.agent))
    sim.events.subscribe(LineShown, lambda event: seen.append(event.agent))
    sim.events.subscribe(AgentFinished, lambda event: seen.append(event.agent))
    run(sim, 10.0)
    assert seen
    for agent in seen:
        assert isinstance(agent, AgentView)
        assert any(agent is live for live in sim.agents)


def test_a_sim_rejects_an_agent_from_another_sim() -> None:
    sim, other = make_sim(), make_sim()
    stranger = other.agents[0]
    with pytest.raises(LarpError, match="not an agent of this sim"):
        sim.elapsed(stranger)
    question = SCENARIOS["prod"].questions[0]
    with pytest.raises(LarpError, match="not an agent of this sim"):
        sim.ask(stranger, question)
