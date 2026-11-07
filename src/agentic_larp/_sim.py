"""The fake agent simulation. Nothing here does any work. That is the point."""

import random
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass, field

from agentic_larp._errors import LarpError
from agentic_larp._grammar import Grammar, parse_activity
from agentic_larp._log import LogLine
from agentic_larp._packs import Scenario

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


@dataclass(frozen=True, slots=True)
class SwarmSettings:
    """How big the swarm is and what its members are called.

    Attributes:
        agents: Lead agents, each with a panel.
        interns: Tiny swarm agents in the bottom strip.
        timescale: Fake seconds that pass per real second.
        lead_model: Name prefix for lead agents.
        intern_model: Name prefix for interns.
    """

    agents: int = 8
    interns: int = 16
    timescale: float = 22.0
    lead_model: str = "maestro"
    intern_model: str = "intern"


@dataclass(slots=True)
class Agent:
    """A lead agent with its own panel and log.

    Attributes:
        name: Display name, such as ``maestro-3``.
        scenario_key: Key of the pack that supplies its activity.
        area: What it is "working" on, such as ``render``.
        files: Files it touches.
        spawn_offset: Fake seconds after the run started that it joined.
        log: Lines already shown in its panel.
        queue: Lines waiting to be streamed into the log.
        tokens: Tokens it has pretended to use.
        calls: Tool calls it has pretended to make.
        verb: Its current spinner verb.
        is_done: Whether it has finished.
        finish_at: Real time it wraps up after the first "ship it".
        frozen_elapsed: Fake elapsed time, fixed once it finishes.
        last_active: Sim time a line last entered its log.
    """

    name: str
    area: str
    files: tuple[str, ...]
    scenario_key: str = ""
    spawn_offset: float = 0.0
    log: deque[LogLine] = field(default_factory=lambda: deque(maxlen=120))
    queue: deque[LogLine] = field(default_factory=deque)
    tokens: int = 0
    calls: int = 0
    verb: str = "Frothing"
    is_done: bool = False
    finish_at: float | None = None
    frozen_elapsed: float | None = None
    last_active: float = 0.0


@dataclass(slots=True)
class Intern:
    """A tiny swarm agent shown as a two-line tile.

    Attributes:
        name: Display name, such as ``intern-07``.
        task: What its tile says it is doing.
        is_done: Whether its tile shows a check mark.
        until: Real time its state next flips.
        frozen_elapsed: Fake elapsed time shown while done.
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
            raise LarpError(message)
        settings = settings or SwarmSettings()
        self.scenarios = list(scenarios)
        self.task = task or self.scenarios[0].task
        self._by_key = {scenario.key: scenario for scenario in self.scenarios}
        self._grammars: dict[tuple[str, str], Grammar] = {}
        self.timescale = settings.timescale
        self.lead_model = settings.lead_model
        self.intern_model = settings.intern_model
        self.rng = rng or random.Random()
        self.orchestrator = self.rng.choice(ORCHESTRATORS)
        self.now = 0.0
        self.fake = self.rng.uniform(4, 9) * 60  # pretend we've been at it a while
        self.energy = 0.0
        self.agents: list[Agent] = []
        self.interns: list[Intern] = []
        self.reports: deque[tuple[str, str]] = deque(maxlen=12)
        self.pending_user: list[str] = []
        for _ in range(settings.agents):
            self.spawn_agent(quiet=True)
        for index in range(settings.interns):
            intern = Intern(name=f"{self.intern_model}-{index + 1:02d}")
            self._assign_intern(intern)
            if self.rng.random() < _INTERNS_DONE_AT_START:
                intern.is_done = True
                intern.frozen_elapsed = self.fake - self.rng.uniform(0, 120)
            self.interns.append(intern)
        for agent in self.agents:
            for _ in range(self.rng.randint(3, 6)):
                self._emit(agent)
            agent.log.extend(agent.queue)
            agent.queue.clear()

    # ---- totals --------------------------------------------------------------
    @property
    def total_tokens(self) -> int:
        """Return every token the swarm has pretended to use."""
        intern_tokens = 7_400 * len(self.interns) * int(1 + self.fake / 300)
        return sum(agent.tokens for agent in self.agents) + intern_tokens

    @property
    def total_calls(self) -> int:
        """Return every tool call the swarm has pretended to make."""
        intern_calls = int(self.fake / 4) * max(1, len(self.interns) // 4)
        return sum(agent.calls for agent in self.agents) + intern_calls

    @property
    def cost(self) -> float:
        """Return the imaginary dollars spent."""
        return self.total_tokens / _TOKENS_PER_DOLLAR

    @property
    def running(self) -> int:
        """Return how many lead agents are still working."""
        return sum(not agent.is_done for agent in self.agents)

    @property
    def is_all_done(self) -> bool:
        """Return whether every lead agent has finished."""
        return all(agent.is_done for agent in self.agents)

    def elapsed(self, agent: Agent) -> float:
        """Return the fake seconds an agent has been working.

        Args:
            agent: One of :attr:`agents`.

        Returns:
            Seconds, frozen once the agent is done.
        """
        if agent.frozen_elapsed is not None:
            return agent.frozen_elapsed
        return max(0.0, self.fake - agent.spawn_offset)

    def spawn_agent(self, *, quiet: bool = False) -> Agent:
        """Add a lead agent, taking the next area in the scenario.

        Args:
            quiet: Seed it as if it had been running from the start, without
                an orchestrator report.

        Returns:
            The new agent.
        """
        index = len(self.agents)
        pack_count = len(self.scenarios)
        scenario = self.scenarios[index % pack_count]
        areas = list(scenario.areas.items())
        area, files = areas[(index // pack_count) % len(areas)]
        agent = Agent(
            name=f"{self.lead_model}-{index + 1}",
            area=area,
            files=files,
            scenario_key=scenario.key,
            spawn_offset=self.rng.uniform(0, 150) if quiet else self.fake,
            verb=self.rng.choice(SPINNER_VERBS),
        )
        if quiet:
            agent.tokens = self.rng.randint(30_000, 90_000)
            agent.calls = self.rng.randint(20, 60)
        else:
            self.reports.append((self.orchestrator, f"spawning {agent.name} → {area}"))
        self.agents.append(agent)
        return agent

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
        self.reports.append(("you", text))
        self.reports.append((self.orchestrator, f"routing to {self.running} agents"))
        self.pending_user.append(text)
        self.poke(6)

    def ship(self) -> None:
        """Have every agent wrap up over the next few seconds."""
        self.reports.append(
            (self.orchestrator, "wrapping up. tell everyone to commit.")
        )
        for agent in self.agents:
            if not agent.is_done and agent.finish_at is None:
                agent.finish_at = self.now + self.rng.uniform(0.6, 4.5)

    # ---- the tick ------------------------------------------------------------
    def tick(self, dt: float) -> None:
        """Advance the simulation.

        Args:
            dt: Real seconds since the previous tick.
        """
        rng = self.rng
        self.now += dt
        self.fake += dt * self.timescale * (1 + self.energy * 0.15)
        boost = 1 + self.energy
        self.energy = max(0.0, self.energy - dt * (2 + self.energy * 0.6))
        for agent in self.agents:
            if not agent.is_done:
                self._tick_agent(agent, dt, boost)
        is_shipping = any(agent.finish_at is not None for agent in self.agents)
        for intern in self.interns:
            if is_shipping:
                if not intern.is_done:
                    intern.is_done, intern.frozen_elapsed = True, self.fake
            elif self.now >= intern.until:
                if intern.is_done:
                    self._assign_intern(intern)
                else:
                    intern.is_done, intern.frozen_elapsed = True, self.fake
                    intern.until = self.now + rng.uniform(1.5, 6) / boost
            elif not intern.is_done and rng.random() < dt * 0.6 * boost:
                self._assign_intern(intern, keep_time=True)

    def _tick_agent(self, agent: Agent, dt: float, boost: float) -> None:
        rng = self.rng
        hurry = 1 if agent.finish_at is None else 4
        if agent.queue and rng.random() < dt * 9 * boost * hurry:
            agent.log.append(agent.queue.popleft())
            agent.last_active = self.now
            agent.calls += 1
            agent.tokens += rng.randint(300, 4_000)
        elif not agent.queue:
            if agent.finish_at is not None and self.now >= agent.finish_at:
                self._finish(agent)
            elif rng.random() < dt * 0.9 * boost * hurry:
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
        if self.interns:
            intern = rng.choice(self.interns).name
        else:
            intern = f"{self.intern_model}-01"
        return {
            "file": file,
            "area": area,
            "agent": agent.name,
            "intern": intern,
            "n": str(rng.choice(_NUMBERS)),
        }

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
            lines = parse_activity(grammar.expand("action", rng, bindings), first_line)
            if self.interns or all(line.label != "Task" for line in lines):
                break
        else:
            lines = [line for line in lines if line.label != "Task"]
        queue.extend(lines)
        if rng.random() < _QUIP_CHANCE:
            quip = grammar.expand("quip", rng, bindings)
            queue.append(LogLine("quip", quip))
            short = file.rsplit("/", 1)[-1]
            self.reports.append((agent.name, f"{short}: {_lower_first(quip)}"))

    def _finish(self, agent: Agent) -> None:
        grammar = self._grammar_for(agent)
        file = self.rng.choice(agent.files)
        final = grammar.expand(
            "final", self.rng, self._bindings(agent, file, agent.area)
        )
        agent.log.append(LogLine("quip", final))
        agent.log.append(LogLine("done", f"✓ {agent.area} done · {agent.calls} calls"))
        agent.last_active = self.now
        agent.frozen_elapsed = self.elapsed(agent)
        agent.is_done = True
        self.reports.append((agent.name, f"done. {_lower_first(final)}"))

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
        intern.task = scenario.grammar.expand("intern_task", rng, bindings)
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
