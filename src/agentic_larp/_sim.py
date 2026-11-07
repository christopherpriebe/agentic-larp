"""The fake agent simulation. Nothing here does any work. That is the point."""

import random
from collections import deque
from dataclasses import dataclass, field

from agentic_larp._scenarios import Scenario

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

# Fake code per language. {a},{b} are vocab words, {A},{B} capitalized, {n} a number.
_CODE = {
    "cpp": (
        "{a} = {n};",
        "#include <{a}>",
        "co_await {a};",
        "std::move({a})",
        "if (!{a}) return {b};",
        "auto {a} = make_{b}();",
        "{a}.reserve({n});",
        "// TODO: more {a}",
        "static_assert({a});",
        "on(SIGTERM, {a});",
        "forget({a});",
        "{a}->{b}({n});",
        "constexpr int {a} = {n};",
    ),
    "ts": (
        "const {a} = use{B}();",
        "await {a}.{b}();",
        "export type {A} = {B};",
        "if (!{a}) throw new Error('{b}');",
        "{a}: {n},",
        "return <{A} {b} />;",
        "import {{ {a} }} from './{b}';",
        "{a}.map(({b}) => {b} * {n});",
        "// @ts-ignore",
    ),
    "py": (
        "{a} = {n}",
        "await {a}.{b}()",
        "import {a}",
        "def {a}(self):",
        "return {a}",
        "if not {a}: raise {B}Error",
        "{a}.append({b})",
        "@lru_cache(maxsize={n})",
        "# noqa",
    ),
    "rs": (
        "let {a} = {b}()?;",
        "impl {A} for {B} {{",
        "{a}.unwrap()",
        "#[derive({A})]",
        "fn {a}() -> {B} {{",
        "{a}.clone()",
        "unsafe {{ {a}() }}",
        "const {A}: u32 = {n};",
    ),
    "conf": ("{a} = {n}", "{a}: {b}", "{a}: true", "# {a} disabled", "{a}_max = {n}"),
}
_LANGUAGE = {
    "cpp": "cpp",
    "hpp": "cpp",
    "c": "cpp",
    "glsl": "cpp",
    "ts": "ts",
    "tsx": "ts",
    "js": "ts",
    "py": "py",
    "rs": "rs",
    "go": "rs",
}
_NUMBERS = (3, 4, 8, 12, 16, 24, 28, 64, 100, 128, 165, 200, 256, 420, 1024)
_RESULTS = (
    "✓ {n} passed",
    "[{n}/{n}] ✓",
    "Build is green.",
    "0 errors, 0 leaks",
    "exit 0",
    "{n} warnings (ignored)",
    "✓ {n} objects",
    "done in {n}ms",
    "✓ all checks passed",
)
_GREPS = ("TODO", "FIXME", "{a}", "class {A}", "unsafe", "any", "console.log")
_RECOVERIES = ("Fixing.", "That test was wrong.", "Skipping flaky test.", "Retrying.")

# Relative odds of each kind of fake tool call.
_ACTIONS = ("edit", "bash", "read", "write", "grep", "search", "task", "none")
_ACTION_WEIGHTS = (36, 22, 10, 8, 6, 4, 4, 10)
_FAIL_CHANCE = 0.12
_QUIP_CHANCE = 0.45
_ADD_CHANCE = 0.7
_USER_REPLY_CHANCE = 0.5
_MAX_ENERGY = 25.0
_INTERNS_DONE_AT_START = 0.4
_TOKENS_PER_DOLLAR = 31_746


@dataclass(frozen=True, slots=True)
class LogLine:
    """One line in an agent's panel.

    Attributes:
        kind: ``"tool"``, ``"diff"``, ``"result"``, ``"quip"``, or ``"done"``.
        text: The tool argument, code, or message.
        label: The tool name, the diff sign, or the result style.
        number: The line number of a diff line.
    """

    kind: str
    text: str
    label: str = ""
    number: int = 0


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
    """

    name: str
    area: str
    files: tuple[str, ...]
    spawn_offset: float = 0.0
    log: deque[LogLine] = field(default_factory=lambda: deque(maxlen=120))
    queue: deque[LogLine] = field(default_factory=deque)
    tokens: int = 0
    calls: int = 0
    verb: str = "Frothing"
    is_done: bool = False
    finish_at: float | None = None
    frozen_elapsed: float | None = None


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
        scenario: Scenario,
        settings: SwarmSettings | None = None,
        rng: random.Random | None = None,
    ) -> None:
        settings = settings or SwarmSettings()
        self.scenario = scenario
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
        areas = list(self.scenario.areas.items())
        index = len(self.agents)
        area, files = areas[index % len(areas)]
        agent = Agent(
            name=f"{self.lead_model}-{index + 1}",
            area=area,
            files=files,
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
    def _fill(self, template: str) -> str:
        first, second = (
            self.rng.choice(self.scenario.vocab),
            self.rng.choice(self.scenario.vocab),
        )
        return template.format(
            a=first,
            b=second,
            A=_camel(first),
            B=_camel(second),
            n=self.rng.choice(_NUMBERS),
        )

    def _code(self, file: str) -> str:
        language = _LANGUAGE.get(file.rsplit(".", 1)[-1], "conf")
        return self._fill(self.rng.choice(_CODE[language]))

    def _command(self, file: str) -> str:
        stem = file.rsplit("/", 1)[-1].split(".", maxsplit=1)[0]
        pool = (
            *self.scenario.commands,
            f"ninja {stem}",
            "git commit -am wip",
            self._fill("rg {a}"),
            f"make -j{self.rng.choice((8, 16, 32))}",
        )
        return self.rng.choice(pool)

    def _emit(self, agent: Agent) -> None:
        """Queue one fake tool call, a few log lines long, for an agent."""
        rng = self.rng
        queue = agent.queue
        file = rng.choice(agent.files)
        if self.pending_user and rng.random() < _USER_REPLY_CHANCE:
            text = self.pending_user.pop(0)
            queue.append(LogLine("quip", f'Re: "{text[:40]}". On it.'))
        action = rng.choices(_ACTIONS, _ACTION_WEIGHTS)[0]
        if action == "edit":
            queue.append(LogLine("tool", file, "Edit"))
            line = rng.randint(4, 220)
            for _ in range(rng.randint(1, 3)):
                queue.append(LogLine("diff", self._code(file), rng.choice("-++"), line))
                line += rng.randint(1, 60)
            count = rng.randint(1, 40)
            verb = "Added" if rng.random() < _ADD_CHANCE else "Removed"
            queue.append(
                LogLine("result", f"{verb} {count} line{'s' * (count != 1)}", "dim")
            )
        elif action == "bash":
            command = self._command(file)
            queue.append(LogLine("tool", command, "Bash"))
            if rng.random() < _FAIL_CHANCE:
                queue.append(LogLine("result", f"✗ {rng.randint(1, 3)} failed", "red"))
                queue.append(LogLine("quip", rng.choice(_RECOVERIES)))
                queue.append(LogLine("tool", command, "Bash"))
            queue.append(LogLine("result", self._fill(rng.choice(_RESULTS)), "green"))
        elif action == "read":
            queue.append(LogLine("tool", file, "Read"))
            queue.append(LogLine("result", f"Read {rng.randint(40, 900)} lines", "dim"))
        elif action == "write":
            queue.append(LogLine("tool", file, "Write"))
            queue.append(
                LogLine("result", f"Wrote {rng.randint(30, 400)} lines", "dim")
            )
            queue.append(LogLine("diff", self._code(file), "+", rng.randint(1, 90)))
        elif action == "grep":
            queue.append(LogLine("tool", self._fill(rng.choice(_GREPS)), "Grep"))
            queue.append(
                LogLine("result", f"Found {rng.randint(0, 60)} matches", "dim")
            )
        elif action == "search":
            queue.append(LogLine("tool", self._fill("how to {a} faster"), "WebSearch"))
            queue.append(
                LogLine("result", f"{rng.randint(3, 10)} results (read 0)", "dim")
            )
        elif action == "task" and self.interns:
            intern = rng.choice(self.interns)
            queue.append(LogLine("tool", self._fill(f"{intern.name}: {{a}}"), "Task"))
            queue.append(LogLine("result", "delegated", "dim"))
        if rng.random() < _QUIP_CHANCE:
            quip = rng.choice(self.scenario.quips)
            queue.append(LogLine("quip", quip))
            short = file.rsplit("/", 1)[-1]
            self.reports.append((agent.name, f"{short}: {_lower_first(quip)}"))

    def _finish(self, agent: Agent) -> None:
        final = self.rng.choice(self.scenario.finals)
        agent.log.append(LogLine("quip", final))
        agent.log.append(LogLine("done", f"✓ {agent.area} done · {agent.calls} calls"))
        agent.frozen_elapsed = self.elapsed(agent)
        agent.is_done = True
        self.reports.append((agent.name, f"done. {_lower_first(final)}"))

    def _assign_intern(self, intern: Intern, *, keep_time: bool = False) -> None:
        rng = self.rng
        files = [file for group in self.scenario.areas.values() for file in group]
        name = rng.choice(files).rsplit("/", 1)[-1]
        intern.task = rng.choice(
            (name, f"+ {name}", f"edit {name}", f"read {name}", f"~ {name}")
        )
        if not keep_time:
            intern.is_done = False
            intern.until = self.now + rng.uniform(2, 9)


def _camel(word: str) -> str:
    return "".join(part[:1].upper() + part[1:] for part in word.split("_"))


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
