# Extending agentic-larp

The 0.1 Python API: events, widgets, apps, meltdowns, stages and the surface
plugins can rely on. For scenario content (packs, questions, toolchains,
policies) see [Writing packs](packs.md). Back to the [README](../README.md).

Every extension point is a Python entry-point group, loaded by one registry
(`agentic_larp.plugins.load_registry`):

| Group | Registers |
| --- | --- |
| `agentic_larp.apps` | payoff apps (`larp --app NAME`, `larp --play NAME`) |
| `agentic_larp.policies` | choice policies (`larp --policy NAME`); see [Choice policies](packs.md#choice-policies) |
| `agentic_larp.widgets` | replacements for the wall's regions |
| `agentic_larp.stages` | stages of the run (`plan`, `work`, `wrap`, `ready`, `ship`, `launch`, `receipt`); a plugin with a built-in's name replaces it |

## Modules

The root `agentic_larp` exports only `main`, `LarpError`, `GrammarError`,
`InvalidValueError` and `__version__`. Everything else is in a submodule, each
with an explicit `__all__`:

| Module | For |
| --- | --- |
| `agentic_larp.cli` | `main`, `build_parser`, `fit_agents`: the `larp` command |
| `agentic_larp.sim` | `Sim`, `SwarmSettings`, `AgentView`, `InternView`, `Todo`, `RunMode`, `LogLine`: the fake swarm |
| `agentic_larp.questions` | `Question` and `Option`, what agents ask and how you answer |
| `agentic_larp.events` | `Event` classes and the `EventBus` a sim publishes on |
| `agentic_larp.stages` | `Session`, `Stage`, `run_flow`, `stage_registry`, `END`, `ABANDON` and the built-in stages; a `ScreenStage` has `on_escape` (escape on an empty prompt) and `on_quit` (a quit word or escape) hooks, which abandon the run by default |
| `agentic_larp.widgets` | `Wall`, `Widget`, `PanelWidget`, the built-in widgets, `widget_registry` |
| `agentic_larp.packs` | `Scenario`, `Grammar`, pack loading, discovery and scenario picking |
| `agentic_larp.policies` | choice policies and `policy_registry` |
| `agentic_larp.apps` | `App`, `AppContext`, `Screen`, `run_loop`, `app_registry`, `discover_apps` |
| `agentic_larp.meltdown` | build and play your app's own meltdown |
| `agentic_larp.keys` | `Keys`, `KeySource`, `parse_keys`, `is_interactive` |
| `agentic_larp.plugins` | `load_registry`, the one loader behind every entry-point group |

## Stable surface

Plugins can rely on these; everything else may change between releases.

- `AgentView` (what events and panel widgets receive): `name`, `area`,
  `files`, `is_done`, `verb`, `finish_at`, `tokens`, `calls`, `todos_done`,
  `todos`, `log` (a collection; use `list(agent.log)[-n:]` for the last
  lines), `last_active`, `scenario_key`. It is read-only for type
  checkers only.
- `InternView` (an intern in the bottom strip): `name`, `task`, `is_done`,
  `frozen_elapsed`. Read-only for type checkers only.
- `SwarmSettings`: `agents`, `interns`, `activity`, `lead_model`,
  `intern_model`, `policy`, `mode`, `length`, and `log_length` (lines each panel
  log keeps, default 120; `None` keeps every line).
- `Sim`: `agents`, `interns`, `reports`, `now`, `task`, `orchestrator`,
  `intern_model`, `events`, `open_question`, `run_time`, `total_tokens`,
  `total_calls`, `cost`, `running`, `is_all_done`, `is_converged`, `length`,
  `scenarios`, `elapsed`, `ask`, `answer`, `report`, `ship`, `start_ship`,
  `spawn_agent`.
- `Wall`: `sim`, `console`, `mode`, `mode_since`, `buffer`, `question_cursor`.

## Events

Events that carry an `agent` hand you an `AgentView` (see [Stable surface](#stable-surface)).

The sim announces what happens on `sim.events`, a typed bus. `subscribe` takes
an event class (subclasses count, so `Event` hears everything) and a handler,
and returns a function that unsubscribes. Handlers run in subscription order
and their exceptions propagate.

```python
unsubscribe = sim.events.subscribe(TodoDone, lambda event: print(event.todo.text))
```

| Event | Fields | When |
| --- | --- | --- |
| `AgentSpawned` | `agent` | an agent is spawned after the sim is created (the starting agents are already in `sim.agents`) |
| `LineShown` | `agent`, `line` | a line enters an agent's log |
| `TodoDone` | `agent`, `todo` | an agent completes a todo |
| `ScopeCreep` | `agent`, `added` | an agent finds more todos |
| `AgentFinished` | `agent`, `final` | an agent wraps up |
| `Converged` | | every agent finished its todos; never once shipping has started, so never after a rush |
| `ShipStarted` | | shipping starts, once: on the first `ship()` (the rush) or when the ready stage ships after convergence (`sim.start_ship()`) |
| `QuestionAsked` | `agent`, `question` | an agent pauses to ask a question (`sim.ask(agent, question)`) |
| `QuestionAnswered` | `agent`, `question`, `option` | the question is answered (`sim.answer(index)`) and the agent resumes |
| `Report` | `who`, `text` | a line for the report feed (`sim.report(who, text)`) |

## Widgets

The wall has five regions: `header`, `swarm`, `question` (height 0 unless a question is open; read `wall.sim.open_question` and `wall.question_cursor`), `footer` and `panel` (one per
agent). A full-width region is a `Widget`, with `height(width, available) ->
int` (rows wanted; 0 hides it) and `render(width)`. The `panel` region is a
`PanelWidget`, with `render(agent)` (an `AgentView`). Each is built once from a factory that
takes the `Wall`, so it can subscribe to `wall.sim.events`. Register a class or
function under the `agentic_larp.widgets` entry-point group, named after the
region it replaces; the rest stay built in.

```toml
[project.entry-points."agentic_larp.widgets"]
footer = "my_package.widgets:Footer"
```

`Wall(sim, console, widgets={"footer": Footer})` does the same in code. A
widget plugin that fails to load, or is named after an unknown region, prints
a warning and is skipped, like stage and app plugins.

## Writing your own app

An app is an `App`: a name, a description and a function that takes an `AppContext`. The usual shape is a screen
object with `render`, `on_key`, and `tick`, driven by `run_loop`:

```python
from rich.text import Text

from agentic_larp.apps import App, AppContext, run_loop


class Counter:
    def __init__(self) -> None:
        self.presses = 0

    def render(self) -> Text:
        return Text(f"you pressed {self.presses} keys. esc to leave.")

    def on_key(self, key: str) -> bool:  # return False to exit
        self.presses += 1
        return key != "esc"

    def tick(self, dt: float) -> bool:  # return False to exit
        return True


def run(context: AppContext) -> None:
    run_loop(context, Counter())


APP = App("counter", "counts your keypresses", run)
```

Register it in your package's `pyproject.toml`; the entry point can be the
`App` itself or a bare `run(context)` function (shown in `--list` as
"plugin"):

```toml
[project.entry-points."agentic_larp.apps"]
counter = "my_package.counter:APP"
```

To add a built-in app, add one new module to `src/agentic_larp/apps/` that
defines `APP`; `discover_apps()` imports every module of the package and
collects each module-level `APP`, so nothing else needs editing.

Then run `larp --app counter` or `larp --play counter`.

An app gets `context.flags` (the `--flag` pairs) and `context.rng` (the
session's random source). Apps melt down only when the `ending` flag is
`meltdown`, and there is no chance involved. The meltdown is a public library,
`agentic_larp.meltdown`, so each app builds its own: a `Meltdown` holds your
`errors` (mixed with `shared` random `SHARED_ERRORS`), your `deaths` (a tuple
of `DeathScreen(lines, style)`; the defaults are `EXIT_137`, `KERNEL_PANIC` and
`BLUE_SCREEN`), your `reveal` and `note` lines, and the length of each phase.
`is_doomed(context)` says whether to break, `play(...)` runs a screen and
melts down if it broke, and `run_meltdown(context, frame, meltdown)` is the
lower-level call. `capture_frame(console, renderable)` turns a renderable into
plain text lines, and `decay(lines, amount, rng)` corrupts a fraction of their
characters (0 to 1; a larger amount corrupts a superset). A plugin with its
own meltdown:

```python
from rich.text import Text

from agentic_larp.apps import AppContext
from agentic_larp.meltdown import DeathScreen, Meltdown, is_doomed, play

MELTDOWN = Meltdown(
    errors=("doomed.py: it was doomed",),
    deaths=(DeathScreen(("DOOMED", "press any key to be doomed"), "white on red"),),
    reveal="jk. doomed.py is fine.",
)


class Doomed:
    def __init__(self, *, doomed: bool) -> None:
        self.doomed = doomed
        self.has_broken = False
        self.seconds = 0.0

    def render(self) -> Text:
        return Text(f"all systems nominal ({self.seconds:.0f}s)")

    def on_key(self, key: str) -> bool:
        return key != "esc"

    def tick(self, dt: float) -> bool:
        self.seconds += dt
        self.has_broken = self.doomed and self.seconds > 5  # break after 5s
        return not self.has_broken


def run(context: AppContext) -> None:
    # play drops auto when doomed, or demo mode would end the app before it
    # breaks; esc before the break just leaves, no meltdown.
    play(
        context,
        Doomed(doomed=is_doomed(context)),
        MELTDOWN,
        success="all systems nominal.",
        failure="it was doomed all along.",
    )
```
