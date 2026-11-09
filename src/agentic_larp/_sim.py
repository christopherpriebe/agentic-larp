"""The fake agent simulation. Nothing here does any work. That is the point."""

import math
import random
from collections import deque
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, runtime_checkable

from agentic_larp._errors import InvalidValueError, LarpError
from agentic_larp._events import (
    AgentFinished,
    AgentSpawned,
    Converged,
    EventBus,
    LineShown,
    QuestionAnswered,
    QuestionAsked,
    Report,
    ScopeCreep,
    ShipStarted,
    TodoDone,
)
from agentic_larp._grammar import Grammar, parse_activity
from agentic_larp._log import LogLine
from agentic_larp._packs import Scenario
from agentic_larp._policies import ChoicePolicy, RandomPolicy
from agentic_larp._questions import Option, Question

SPINNER_VERBS = (
    "Frothing",
    "Steeping",
    "Orchestrating",
    "Vibing",
    "Reticulating",
    "Percolating",
    "Manifesting",
    "Synergizing",
    "Marinating",
    "Cogitating",
    "Noodling",
    "Simmering",
    "Hallucinating",
    "Yak-shaving",
    "Bikeshedding",
    "Grokking",
    "Spelunking",
)
ORCHESTRATORS = ("astra", "atlas", "nova", "orion", "vega", "maestro", "conductor")

_NUMBERS = (3, 4, 8, 12, 16, 24, 28, 64, 100, 128, 165, 200, 256, 420, 1024)
_QUIP_CHANCE = 0.45
_REROLLS = 20
_USER_REPLY_CHANCE = 0.5
_MAX_ENERGY = 25.0
_INTERNS_DONE_AT_START = 0.4
_TOKENS_PER_DOLLAR = 31_746
_AGENT_TOKENS_PER_SECOND = 2_000
_INTERN_TOKENS_PER_SECOND = 800
_INTERN_START_TOKENS = 7_400
_SECONDS_PER_INTERN_CALL = 4
_INTERNS_PER_CALLER = 4
_TOKEN_EPOCH = 300
_MAX_REPORTS = 12
_MIN_TODOS = 3
_MAX_TODOS = 6
_MAX_CREEP = 3
_SPEED_SPREAD = 0.2
_CREEP_SPREAD = 0.25
_TODO_SHARE = (0.5, 1.5)
_MIN_IDLE = 0.5
_MAX_IDLE = 1.7


DEFAULT_LOG_LENGTH = 120


class RunMode(StrEnum):
    """Whether the swarm converges on its own or creeps forever."""

    CONVERGE = "converge"
    ENDLESS = "endless"


@dataclass(frozen=True, slots=True)
class Todo:
    """One item on an agent's todo list.

    Attributes:
        text: What the item says.
        seconds: Seconds of work it takes at activity 1.

    Raises:
        InvalidValueError: If ``text`` is blank or ``seconds`` is not a finite number
            above 0.
    """

    text: str
    seconds: float

    def __post_init__(self) -> None:
        if not self.text.strip():
            message = "a todo needs text"
            raise InvalidValueError(message)
        if not math.isfinite(self.seconds) or self.seconds <= 0:
            message = (
                f"a todo's seconds must be a finite number above 0, not {self.seconds}"
            )
            raise InvalidValueError(message)


@dataclass(frozen=True, slots=True)
class SwarmSettings:
    """How big the swarm is and what its members are called.

    Attributes:
        agents: Lead agents, each with a panel.
        interns: Tiny swarm agents in the bottom strip.
        activity: How fast the agents work; never affects the clock.
        lead_model: Name prefix for lead agents.
        intern_model: Name prefix for interns.
        policy: Factory for the choice policy; each lead agent and each
            intern gets its own instance.
        mode: Whether the agents finish their todos and stop, or keep finding
            more.
        length: Target seconds for the swarm to converge at activity 1.
        log_length: Lines each panel log keeps; ``None`` keeps every line.

    Raises:
        InvalidValueError: If ``activity`` or ``length`` is not a finite number above
            0, ``agents`` is below 1, ``interns`` is below 0, or
            ``log_length`` is not an int or is set below 1.
    """

    agents: int = 8
    interns: int = 16
    activity: float = 1.0
    lead_model: str = "maestro"
    intern_model: str = "intern"
    policy: Callable[[], ChoicePolicy] = RandomPolicy
    mode: RunMode = RunMode.CONVERGE
    length: float = 20.0
    log_length: int | None = DEFAULT_LOG_LENGTH

    def __post_init__(self) -> None:
        if not math.isfinite(self.activity) or self.activity <= 0:
            message = "activity must be a finite number above 0"
            raise InvalidValueError(message)
        if not math.isfinite(self.length) or self.length <= 0:
            message = "length must be a finite number above 0"
            raise InvalidValueError(message)
        if self.agents < 1:
            message = "a swarm needs at least one agent"
            raise InvalidValueError(message)
        if self.interns < 0:
            message = f"interns must be at least 0, not {self.interns}"
            raise InvalidValueError(message)
        if self.log_length is not None and (
            not isinstance(self.log_length, int) or isinstance(self.log_length, bool)
        ):
            message = f"log_length must be an int or None, not {self.log_length!r}"
            raise InvalidValueError(message)
        if self.log_length is not None and self.log_length < 1:
            message = f"log_length must be at least 1 or None, not {self.log_length}"
            raise InvalidValueError(message)


@runtime_checkable
class AgentView(Protocol):
    """The stable, read-only view of an agent that events and widgets hand to plugins.

    Read-only is enforced by type checkers only.
    """

    @property
    def name(self) -> str:
        """Return the display name, such as ``maestro-3``."""
        ...

    @property
    def area(self) -> str:
        """Return what the agent is "working" on, such as ``render``."""
        ...

    @property
    def files(self) -> tuple[str, ...]:
        """Return the files it touches."""
        ...

    @property
    def is_done(self) -> bool:
        """Return whether it has finished."""
        ...

    @property
    def verb(self) -> str:
        """Return its current spinner verb."""
        ...

    @property
    def finish_at(self) -> float | None:
        """Return the sim time it wraps up at, or ``None`` before the first "ship it"."""
        ...

    @property
    def tokens(self) -> float:
        """Return the tokens it has pretended to use."""
        ...

    @property
    def calls(self) -> int:
        """Return the tool calls it has pretended to make."""
        ...

    @property
    def todos_done(self) -> int:
        """Return how many todos it has completed."""
        ...

    @property
    def todos(self) -> Sequence[Todo]:
        """Return its todo list."""
        ...

    @property
    def log(self) -> Collection[LogLine]:
        """Return the lines already shown in its panel.

        The collection cannot be sliced; use ``list(agent.log)[-n:]`` for the
        last ``n`` lines.
        """
        ...

    @property
    def last_active(self) -> float:
        """Return the sim time a line last entered its log."""
        ...

    @property
    def scenario_key(self) -> str:
        """Return the key of the pack that supplies its activity."""
        ...


@runtime_checkable
class InternView(Protocol):
    """The stable, read-only view of an intern.

    Read-only is enforced by type checkers only.
    """

    @property
    def name(self) -> str:
        """Return the display name, such as ``intern-07``."""
        ...

    @property
    def task(self) -> str:
        """Return what its tile says it is doing."""
        ...

    @property
    def is_done(self) -> bool:
        """Return whether its tile shows a check mark."""
        ...

    @property
    def frozen_elapsed(self) -> float:
        """Return the run time shown while done."""
        ...


@dataclass(slots=True, eq=False)
class Agent:
    """A lead agent with its own panel and log.

    Internal: plugins see it only as an :class:`AgentView`.

    Attributes:
        name: Display name, such as ``maestro-3``.
        scenario_key: Key of the pack that supplies its activity.
        area: What it is "working" on, such as ``render``.
        files: Files it touches.
        spawn_offset: Seconds of run time at which it joined.
        log: Lines already shown in its panel.
        queue: Lines waiting to be streamed into the log.
        tokens: Tokens it has pretended to use.
        calls: Tool calls it has pretended to make.
        verb: Its current spinner verb.
        is_done: Whether it has finished.
        finish_at: Sim time (``Sim.now``) it wraps up after the first "ship it".
        frozen_elapsed: Run time it worked for, fixed once it finishes.
        last_active: Sim time a line last entered its log.
        todos: Its todo list.
        todos_done: How many todos it has completed.
        work: Boosted seconds it has worked.
        todo_average: Average seconds of its original todos.
        idle: Boosted seconds spent waiting to start the next tool call.
        idle_target: Boosted seconds it waits before the next tool call.
    """

    name: str
    area: str
    files: tuple[str, ...]
    scenario_key: str = ""
    spawn_offset: float = 0.0
    log: deque[LogLine] = field(
        default_factory=lambda: deque(maxlen=DEFAULT_LOG_LENGTH)
    )
    queue: deque[LogLine] = field(default_factory=deque)
    tokens: float = 0.0
    calls: int = 0
    verb: str = "Frothing"
    is_done: bool = False
    finish_at: float | None = None
    frozen_elapsed: float | None = None
    last_active: float = 0.0
    todos: list[Todo] = field(default_factory=list)
    todos_done: int = 0
    work: float = 0.0
    todo_average: float = 1.0
    idle: float = 0.0
    idle_target: float = 1.0


@dataclass(slots=True)
class Intern:
    """A tiny swarm agent shown as a two-line tile.

    Internal: plugins see it only as an :class:`InternView`.

    Attributes:
        name: Display name, such as ``intern-07``.
        task: What its tile says it is doing.
        is_done: Whether its tile shows a check mark.
        until: Real time its state next flips.
        frozen_elapsed: Run time shown while done.
    """

    name: str
    task: str = ""
    is_done: bool = False
    until: float = 0.0
    frozen_elapsed: float = 0.0


class Sim:
    """A swarm of agents that look busy.

    Call :meth:`tick` every frame with the real seconds elapsed. Keypresses go
    to :meth:`poke`, submitted text to :meth:`broadcast`, and the first
    "ship it" to :meth:`ship`.
    """

    def __init__(
        self,
        scenarios: Sequence[Scenario],
        settings: SwarmSettings | None = None,
        rng: random.Random | None = None,
        *,
        task: str | None = None,
    ) -> None:
        if not scenarios:
            message = "a simulation needs at least one pack"
            raise InvalidValueError(message)
        settings = settings or SwarmSettings()
        self.scenarios = list(scenarios)
        self.task = task or self.scenarios[0].task
        self._by_key = {scenario.key: scenario for scenario in self.scenarios}
        self._grammars: dict[tuple[str, str], Grammar] = {}
        self._policy_factory = settings.policy
        self._policies: dict[str, ChoicePolicy] = {}
        self._intern_policies: dict[str, ChoicePolicy] = {}
        self.activity = settings.activity
        self.mode = settings.mode
        self._length = settings.length
        self.lead_model = settings.lead_model
        self.intern_model = settings.intern_model
        self.rng = rng or random.Random()
        self.orchestrator = self.rng.choice(ORCHESTRATORS)
        self.now = 0.0
        self._run_time = self.rng.uniform(4, 9) * 60  # pretend we've been at it a while
        self.energy = 0.0
        self._log_length = settings.log_length
        self._agents: list[Agent] = []
        self._interns: list[Intern] = []
        self.events = EventBus()
        self.reports: deque[tuple[str, str]] = deque(maxlen=_MAX_REPORTS)
        self._is_ship_started = self._is_rushed = self._is_converged_published = False
        self.pending_user: list[str] = []
        self._question: tuple[Agent, Question] | None = None
        for _ in range(settings.agents):
            self.spawn_agent(quiet=True)
        for index in range(settings.interns):
            intern = Intern(name=f"{self.intern_model}-{index + 1:02d}")
            self._intern_policies[intern.name] = self._policy_factory()
            self._assign_intern(intern)
            if self.rng.random() < _INTERNS_DONE_AT_START:
                intern.is_done = True
                intern.frozen_elapsed = self._run_time - self.rng.uniform(0, 120)
            self._interns.append(intern)
        self._intern_tokens = float(
            _INTERN_START_TOKENS
            * len(self._interns)
            * int(1 + self._run_time / _TOKEN_EPOCH)
        )
        self._intern_calls = float(
            int(self._run_time / _SECONDS_PER_INTERN_CALL * self._intern_callers)
        )
        for agent in self._agents:
            for _ in range(self.rng.randint(3, 6)):
                self._emit(agent)
            while agent.queue:
                self._show(agent, agent.queue.popleft())

    # ---- totals --------------------------------------------------------------
    @property
    def run_time(self) -> float:
        """Return the seconds the header clock shows: a fake head start plus real time since the sim started."""
        return self._run_time

    @property
    def length(self) -> float:
        """Return the seconds the swarm takes to converge at activity 1."""
        return self._length

    @property
    def open_question(self) -> tuple[AgentView, Question] | None:
        """Return the agent waiting for an answer and its question, if any."""
        return self._question

    @property
    def _intern_callers(self) -> float:
        return len(self._interns) / _INTERNS_PER_CALLER

    @property
    def total_tokens(self) -> int:
        """Return every token the swarm has pretended to use."""
        return round(sum(agent.tokens for agent in self._agents) + self._intern_tokens)

    @property
    def total_calls(self) -> int:
        """Return every tool call the swarm has pretended to make."""
        return sum(agent.calls for agent in self._agents) + int(self._intern_calls)

    @property
    def cost(self) -> float:
        """Return the imaginary dollars spent."""
        return self.total_tokens / _TOKENS_PER_DOLLAR

    @property
    def running(self) -> int:
        """Return how many lead agents are still working."""
        return sum(not agent.is_done for agent in self._agents)

    @property
    def is_all_done(self) -> bool:
        """Return whether every lead agent has finished."""
        return all(agent.is_done for agent in self._agents)

    @property
    def is_converged(self) -> bool:
        """Return whether every agent finished all its todos without a rush."""
        return (
            self.mode is RunMode.CONVERGE
            and not self._is_rushed
            and self.is_all_done
            and all(agent.todos_done == len(agent.todos) for agent in self._agents)
        )

    @property
    def agents(self) -> Sequence[AgentView]:
        """Return the lead agents, in spawn order."""
        return self._agents

    @property
    def interns(self) -> Sequence[InternView]:
        """Return the interns in the bottom strip."""
        return self._interns

    def _resolve(self, agent: AgentView) -> Agent:
        for candidate in self._agents:
            if candidate is agent:
                return candidate
        message = f"{agent.name!r} is not an agent of this sim"
        raise LarpError(message)

    def elapsed(self, agent: AgentView) -> float:
        """Return the seconds an agent has been working.

        Args:
            agent: One of :attr:`agents`.

        Returns:
            Seconds, frozen once the agent is done.

        Raises:
            LarpError: If ``agent`` is not one of :attr:`agents`.
        """  # noqa: DOC502 - the error comes from a helper this calls; callers still need to know
        agent = self._resolve(agent)
        if agent.frozen_elapsed is not None:
            return agent.frozen_elapsed
        return max(0.0, self._run_time - agent.spawn_offset)

    def spawn_agent(self, *, quiet: bool = False) -> AgentView:
        """Add a lead agent, taking the next area in the scenario.

        Args:
            quiet: Seed it as if it had been running from the start, without
                an orchestrator report.

        Returns:
            The new agent.
        """
        index = len(self._agents)
        pack_count = len(self.scenarios)
        scenario = self.scenarios[index % pack_count]
        areas = list(scenario.areas.items())
        area, files = areas[(index // pack_count) % len(areas)]
        agent = Agent(
            name=f"{self.lead_model}-{index + 1}",
            area=area,
            files=files,
            scenario_key=scenario.key,
            log=deque(maxlen=self._log_length),
            spawn_offset=self.rng.uniform(0, 150) if quiet else self._run_time,
            verb=self.rng.choice(SPINNER_VERBS),
        )
        self._policies[agent.name] = self._policy_factory()
        self._write_todos(agent)
        agent.idle_target = self.rng.uniform(_MIN_IDLE, _MAX_IDLE)
        if quiet:
            agent.tokens = float(self.rng.randint(30_000, 90_000))
            agent.calls = self.rng.randint(20, 60)
        else:
            self.report(self.orchestrator, f"spawning {agent.name} → {area}")
        self._agents.append(agent)
        self.events.publish(AgentSpawned(agent))
        return agent

    def report(self, who: str, text: str) -> None:
        """Add a line to the report feed and announce it.

        Args:
            who: The speaker.
            text: What they said.
        """
        self.reports.append((who, text))
        self.events.publish(Report(who, text))

    def _show(self, agent: Agent, line: LogLine) -> None:
        agent.log.append(line)
        self.events.publish(LineShown(agent, line))

    # ---- input ---------------------------------------------------------------
    def poke(self, amount: float = 1.0) -> None:
        """Register a keypress. Mashing keys makes the agents frantic.

        Args:
            amount: How much frenzy to add.
        """
        self.energy = min(_MAX_ENERGY, self.energy + amount)

    def broadcast(self, text: str) -> None:
        """Route something the user typed to the agents, who are on it.

        Args:
            text: What the user typed.
        """
        self.report("you", text)
        self.report(self.orchestrator, f"routing to {self.running} agents")
        self.pending_user.append(text)
        self.poke(6)

    def start_ship(self) -> None:
        """Announce that shipping has started; later calls do nothing."""
        if not self._is_ship_started:
            self._is_ship_started = True
            self.events.publish(ShipStarted())

    def ship(self) -> None:
        """Have every agent wrap up over the next few seconds.

        An open question is answered with its recommended option first, as
        if you had pressed esc, so its agent can wrap up too.
        """
        if self._question is not None:
            self.answer(self._question[1].recommended)
        self.start_ship()
        self._is_rushed = True
        self.report(self.orchestrator, "wrapping up. tell everyone to commit.")
        for agent in self._agents:
            if not agent.is_done and agent.finish_at is None:
                agent.finish_at = self.now + self.rng.uniform(0.6, 4.5)

    # ---- questions -----------------------------------------------------------
    def ask(self, agent: AgentView, question: Question) -> None:
        """Pause an agent until its question is answered.

        Args:
            agent: Who asks; it does nothing until :meth:`answer`.
            question: What it asks.

        Raises:
            LarpError: If ``agent`` is not one of :attr:`agents`, a question is
                already open, or shipping has started.
        """
        agent = self._resolve(agent)
        if self._is_ship_started:
            message = "shipping has started; no more questions"
            raise LarpError(message)
        if self._question is not None:
            message = f"a question is already open ({self._question[1].key!r})"
            raise LarpError(message)
        self._question = (agent, question)
        self.events.publish(QuestionAsked(agent, question))

    def answer(self, index: int) -> Option:
        """Answer the open question and let its agent get back to work.

        The option's todos and spawns happen here; its flags are the
        caller's to apply.

        Args:
            index: Which option, from 0.

        Returns:
            The chosen option.

        Raises:
            LarpError: If no question is open or the index is out of range.
        """
        if self._question is None:
            message = "no question is open"
            raise LarpError(message)
        agent, question = self._question
        if not 0 <= index < len(question.options):
            message = f"no option {index}; the question has {len(question.options)}"
            raise LarpError(message)
        option = question.options[index]
        if option.todos:
            rng = self.rng
            agent.todos.extend(
                self._draft_todos(
                    agent,
                    [
                        agent.todo_average
                        * rng.uniform(1 - _CREEP_SPREAD, 1 + _CREEP_SPREAD)
                        for _ in range(option.todos)
                    ],
                )
            )
        for _ in range(option.spawn):
            self.spawn_agent()
        self._question = None
        self.events.publish(QuestionAnswered(agent, question, option))
        return option

    # ---- the tick ------------------------------------------------------------
    def idle(self, dt: float) -> None:
        """Run the header clock without doing any work.

        Args:
            dt: Seconds to add to the run time.
        """
        self._run_time += dt

    def tick(self, dt: float) -> None:
        """Advance the simulation.

        Args:
            dt: Real seconds since the previous tick.
        """
        rng = self.rng
        self.now += dt
        if self.is_all_done:
            return
        self._run_time += dt
        boost = (1 + self.energy) * self.activity
        self.energy = max(0.0, self.energy - dt * (2 + self.energy * 0.6))
        asker = None if self._question is None else self._question[0]
        for agent in self._agents:
            if not agent.is_done and agent is not asker:
                self._tick_agent(agent, dt, boost)
        if self.running == 0:
            self._stop_interns()
            return
        self._intern_tokens += (
            len(self._interns) * _INTERN_TOKENS_PER_SECOND * dt * boost
        )
        self._intern_calls += (
            self._intern_callers * dt * boost / _SECONDS_PER_INTERN_CALL
        )
        is_shipping = any(agent.finish_at is not None for agent in self._agents)
        for intern in self._interns:
            if is_shipping:
                if not intern.is_done:
                    intern.is_done, intern.frozen_elapsed = True, self._run_time
            elif self.now >= intern.until:
                if intern.is_done:
                    self._assign_intern(intern)
                else:
                    intern.is_done, intern.frozen_elapsed = True, self._run_time
                    intern.until = self.now + rng.uniform(1.5, 6) / boost
            elif not intern.is_done and rng.random() < dt * 0.6 * boost:
                self._assign_intern(intern, keep_time=True)

    def _stop_interns(self) -> None:
        for intern in self._interns:
            if not intern.is_done:
                intern.is_done, intern.frozen_elapsed = True, self._run_time

    def _tick_agent(self, agent: Agent, dt: float, boost: float) -> None:
        rng = self.rng
        hurry = 1 if agent.finish_at is None else 4
        agent.tokens += _AGENT_TOKENS_PER_SECOND * dt * boost
        agent.work += dt * boost
        if self._advance_todos(agent):
            return
        if agent.queue and rng.random() < dt * 9 * boost * hurry:
            self._show(agent, agent.queue.popleft())
            agent.last_active = self.now
            agent.calls += 1
        elif not agent.queue:
            is_rushed = agent.finish_at is not None and self.now >= agent.finish_at
            if is_rushed:
                self._finish(agent)
            else:
                agent.idle += dt * boost * hurry
                if agent.idle >= agent.idle_target:
                    agent.idle = 0.0
                    agent.idle_target = rng.uniform(_MIN_IDLE, _MAX_IDLE)
                    self._emit(agent)
        if rng.random() < dt * 0.08:
            agent.verb = rng.choice(SPINNER_VERBS)

    # ---- content -------------------------------------------------------------
    def _grammar_for(self, agent: Agent) -> Grammar:
        key = (agent.scenario_key, agent.area)
        if key not in self._grammars:
            scenario = self._by_key[agent.scenario_key]
            self._grammars[key] = scenario.grammar_for(agent.area)
        return self._grammars[key]

    def _bindings(self, agent: Agent, file: str, area: str) -> dict[str, str]:
        rng = self.rng
        if self._interns:
            intern = rng.choice(self._interns).name
        else:
            intern = f"{self.intern_model}-01"
        return {
            "file": file,
            "area": area,
            "agent": agent.name,
            "intern": intern,
            "n": str(rng.choice(_NUMBERS)),
        }

    def _write_todos(self, agent: Agent) -> None:
        """Give an agent a todo list that adds up to its deadline."""
        rng = self.rng
        deadline = self._length * rng.uniform(1 - _SPEED_SPREAD, 1 + _SPEED_SPREAD)
        shares = [
            rng.uniform(*_TODO_SHARE)
            for _ in range(rng.randint(_MIN_TODOS, _MAX_TODOS))
        ]
        agent.todo_average = deadline / len(shares)
        agent.todos = self._draft_todos(
            agent, [deadline * share / sum(shares) for share in shares]
        )

    def _draft_todos(self, agent: Agent, seconds: list[float]) -> list[Todo]:
        rng = self.rng
        grammar = self._grammar_for(agent)
        return [
            Todo(
                grammar.expand(
                    "todo",
                    rng,
                    self._bindings(agent, rng.choice(agent.files), agent.area),
                    policy=self._policies[agent.name],
                ),
                amount,
            )
            for amount in seconds
        ]

    def _advance_todos(self, agent: Agent) -> bool:
        """Complete the todos the agent's work has paid for.

        Returns:
            Whether the agent finished.
        """
        while agent.todos_done < len(agent.todos):
            due = sum(todo.seconds for todo in agent.todos[: agent.todos_done + 1])
            if agent.work < due:
                return False
            agent.todos_done += 1
            self.events.publish(TodoDone(agent, agent.todos[agent.todos_done - 1]))
            if agent.todos_done < len(agent.todos):
                continue
            if self.mode is RunMode.CONVERGE:
                self._finish(agent)
                return True
            self._creep(agent)
        return False

    def _creep(self, agent: Agent) -> None:
        rng = self.rng
        extra = rng.randint(1, _MAX_CREEP)
        average = agent.todo_average
        added = self._draft_todos(
            agent,
            [
                average * rng.uniform(1 - _CREEP_SPREAD, 1 + _CREEP_SPREAD)
                for _ in range(extra)
            ],
        )
        agent.todos.extend(added)
        noun = "thing" if extra == 1 else "things"
        self.report(
            self.orchestrator, f"scope creep: {agent.name} found {extra} more {noun}"
        )
        self.events.publish(ScopeCreep(agent, tuple(added)))

    def _emit(self, agent: Agent) -> None:
        """Queue one fake tool call, a few log lines long, for an agent."""
        rng = self.rng
        queue = agent.queue
        grammar = self._grammar_for(agent)
        file = rng.choice(agent.files)
        bindings = self._bindings(agent, file, agent.area)
        if self.pending_user and rng.random() < _USER_REPLY_CHANCE:
            text = self.pending_user.pop(0)
            queue.append(LogLine("quip", f'Re: "{text[:40]}". On it.'))
        first_line = rng.randint(4, 220)
        for _ in range(_REROLLS):
            lines = parse_activity(
                grammar.expand(
                    "action", rng, bindings, policy=self._policies[agent.name]
                ),
                first_line,
            )
            if self._interns or all(line.label != "Task" for line in lines):
                break
        else:
            lines = [line for line in lines if line.label != "Task"]
        queue.extend(lines)
        if rng.random() < _QUIP_CHANCE:
            quip = grammar.expand(
                "quip", rng, bindings, policy=self._policies[agent.name]
            )
            queue.append(LogLine("quip", quip))
            short = file.rsplit("/", 1)[-1]
            self.report(agent.name, f"{short}: {_lower_first(quip)}")

    def _finish(self, agent: Agent) -> None:
        grammar = self._grammar_for(agent)
        file = self.rng.choice(agent.files)
        final = grammar.expand(
            "final",
            self.rng,
            self._bindings(agent, file, agent.area),
            policy=self._policies[agent.name],
        )
        agent.last_active = self.now
        agent.frozen_elapsed = self.elapsed(agent)
        agent.is_done = True
        self._show(agent, LogLine("quip", final))
        self._show(agent, LogLine("done", f"✓ {agent.area} done · {agent.calls} calls"))
        self.report(agent.name, f"done. {_lower_first(final)}")
        self.events.publish(AgentFinished(agent, final))
        if self.is_converged and not self._is_converged_published:
            self._is_converged_published = True
            self.events.publish(Converged())

    def _assign_intern(self, intern: Intern, *, keep_time: bool = False) -> None:
        rng = self.rng
        scenario = rng.choice(self.scenarios)
        area = rng.choice(list(scenario.areas))
        files = [file for group in scenario.areas.values() for file in group]
        bindings = {
            "file": rng.choice(files).rsplit("/", 1)[-1],
            "area": area,
            "agent": intern.name,
            "intern": intern.name,
            "n": str(rng.choice(_NUMBERS)),
        }
        intern.task = scenario.grammar.expand(
            "intern_task", rng, bindings, policy=self._intern_policies[intern.name]
        )
        if not keep_time:
            intern.is_done = False
            intern.until = self.now + rng.uniform(2, 9)


def _lower_first(text: str) -> str:
    return text[:1].lower() + text[1:]


def format_duration(seconds: float) -> str:
    """Format seconds the way agent dashboards do.

    Args:
        seconds: A duration.

    Returns:
        ``"42s"``, ``"3m 7s"``, or ``"1h 12m"``.
    """
    whole = int(seconds)
    hours, remainder = divmod(whole, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m {secs}s" if minutes else f"{secs}s"


def format_tokens(count: float) -> str:
    """Format a token count compactly.

    Args:
        count: A number of tokens.

    Returns:
        ``"950"``, ``"12.3k"``, or ``"1.24M"``.
    """
    if count >= 1_000_000:  # noqa: PLR2004 - one million is the unit boundary
        return f"{count / 1_000_000:.2f}M"
    if count >= 1_000:  # noqa: PLR2004 - one thousand is the unit boundary
        return f"{count / 1_000:.1f}k"
    return str(int(count))
