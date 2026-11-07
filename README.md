# agentic-larp

> **This entire project is vibe coded.** Every line of code, test, and doc was
> generated with [Claude Code](https://claude.com/claude-code). A human typed
> `ship it`.

Inspired by [programmergrind](https://www.tiktok.com/@programmergrind) on
TikTok, whose agent swarms ship faster than anyone's. Go watch them.

Cosplay as a 10x AI engineer.

`larp` fills your terminal with a wall of AI agents editing files, running
tests, delegating to interns, and burning money in parallel. None of it is
real. Nothing is being built. Type `ship it`, the agents wrap up, type `ship it`
again, and something launches.

```text
❯ astra  build me a girlfriend ───────────── ✶ orchestrating 8 · 27m 3s · ↓ 1.24M · $39.06
maestro-4  heart.hpp: drama: 0 (was 3)
maestro-1  face.cpp: she is gorgeous now.
╭─ ✻ maestro-1 · render ─────────────╮╭─ ✳ maestro-2 · voice ──────────────╮
│ ● Bash(ninja face)                 ││ ● Edit(tts.cpp)                    │
│   ⎿  ✓ 28 objects                  ││  16 - rate = 200;                  │
│ She is gorgeous now.               ││ 171 + rate = 165;                  │
╰─ 26m 27s · ↓ 100.6k · Frothing… ───╯╰─ 27m 4s · ↓ 87.5k · Steeping… ────╯
 intern ×16 ─────────────────────────────────────────────────────────────────
intern-01 ✓    intern-02 ✶    intern-03 ✓    intern-04 ✳    intern-05 ✓
✓ 5m 29s       + face.cpp     ✓ 8m 4s        ring.cpp       ✓ 8m 18s
❯ ship it█                            8/8 running · 1,669 calls
```

## Installation

```console
uv tool install agentic-larp     # or: pipx install agentic-larp
```

It needs Python 3.11 or newer and a terminal that can draw Unicode. Its only
runtime dependency is [Rich](https://github.com/Textualize/rich).

## Usage

```console
larp                              # random scenario
larp "build me a girlfriend"      # scenario picked from keywords in your task
larp "uber for cats"              # anything else: agents work on cats.ts, Uber.tsx, ...
larp -s hacker                    # force a scenario
larp -s hacker -s prod            # mix packs: agents alternate between them
larp --policy varied              # no back-to-back repeats in the agents' output
larp --grid 3x2                   # six feeds on screen, a spotlight rotates through the rest
larp --pack ./zebra.toml -s zebra # your own pack
larp --then "cmatrix"             # after shipping, run any real command
larp --play hacker                # skip the agents, go straight to an app
larp --length 40                  # the swarm takes about 40s to converge (default 20)
larp --forever                    # never converges: the agents keep finding more to do
larp --auto 8                     # ships itself after 8s of work (for screen recordings)
larp --flag ending=meltdown       # the payoff app breaks, then melts down (jk)
larp --list                       # scenarios and apps
```

While it runs:

| You do | It does |
| --- | --- |
| type `ship it` ⏎ | every agent wraps up and reports done |
| type `ship it` again (or ⏎) | `git push --force`, then the payoff app launches |
| type anything else ⏎ | the orchestrator "routes" it; the agents are on it |
| type `spawn` ⏎ | one more agent joins (only while the agents are still running) |
| esc | dismiss the agents |

The prompt at the bottom is you messaging the orchestrator, the lead agent
named in the header. The clock in the header always runs in real time, and it
stops once every agent is done.

Other options: `-n` sets the number of lead agents (default: whatever fits),
`-i` the number of interns (0 hides them), and `--speed` how fast the agents
work (the clock, `--auto`, and every other timing are real seconds). Want
different names on the panels? `--lead-model` and `--intern-model` set them,
for example `--lead-model fable --intern-model sonnet`.

Each run opens with a plan: a `TodoWrite` screen listing every agent's todo
list (3 to 6 items each), which any key skips (the key still goes to the
prompt, so you can start typing `ship it` right away) and which moves on by
itself after two seconds. Todos are timed work: each agent has a deadline of
about `--length` seconds (0.8 to 1.2 times it, per agent) split across its
todos, and it works through them at the pace of `--speed` and your typing, so
they finish staggered, between half and one and a half times `--length`, and
the prompt goes straight to "ship it?". Type `ship it` early to rush them
instead. With `--forever` they never converge: each time an agent finishes its
list the orchestrator reports some scope creep and it gets 1 to 3 more todos
of the original size. Each panel title shows its progress as `done/total`.

When stdin is not a terminal (piped, in CI), `larp` ships itself after six
seconds of work (`--auto` counts work time after the plan, not the plan itself).

### Scenarios and apps

| Scenario | The agents are "building" | After you ship |
| --- | --- | --- |
| `girlfriend` | `face.cpp`, `heart.hpp`, `ring.cpp` | **call**: she calls. Answer, and type to her. |
| `startup` | `Deck.tsx`, `valuation.ts`, `moat.ts` | **stonks**: your ticker, which only goes up |
| `hacker` | `exploit.c`, `payload.asm`, `proxy.go` | **hacker**: scan, dump memory, crack a password, outrun the trace |
| `prod` | `migrations/0042.sql`, `main.tf` | **deploy**: a global rollout; nobody gets paged |
| `dropship` | `products.json`, `checkout.liquid`, `meta_ads.py` | **dropship**: a store dashboard; markups of 1,500%, shipping in 6-8 weeks |
| `memecoin` | `Token.sol`, `add_liquidity.ts`, `hype_bot.py` | **memecoin**: a token launch; the liquidity is locked (trust me) |
| `wrapper` | `system_prompt.txt`, `llm_client.ts`, `pricing.ts` | **wrapper**: an AI startup racing its MRR against its API bill |
| `nft` | `ape_001.png.md`, `Collection.sol`, `ipfs_pin.ts` | **nft**: a pixel ape minting row by row; mind the floor |
| `thoughtleader` | `hook_v12_final.md`, `one_sentence_per_line.ts`, `the_barista_story.md` | **thoughtleader**: a professional-network post that writes itself, one sentence per line. Agree? |
| `clipfarm` | `transcript_3h14m.txt`, `clip_912.mp4.md`, `one_word_at_a_time.ts` | **clipfarm**: one 3-hour podcast becomes 912 vertical clips with one idea |
| `matchmaker` | `simulate_us.py`, `compatibility.py`, `expiry_timer.py` | **matchmaker**: the system assigns your match, and when it expires |
| `generic` | whatever you typed | deploy or stonks |

The hacker app plays four stages by itself (SCANNING, DUMPING MEMORY, CRACKING
PASSWORD, TRACING) and ends on a flashing ACCESS GRANTED after roughly 25
seconds. Every keypress pushes it forward, so mashing keys finishes sooner. Tab
flashes ACCESS GRANTED at any time and esc logs off. When failing, the hack
never promises access: tab flashes ACCESS DENIED and the footer says
`tab: access denied`.

### Failing on purpose

Apps never break on their own. `--flag ending=meltdown` forces the meltdown;
`--flag ending=success` (or no flag) keeps the normal ending, and any other
value is an error. `--flag KEY=VALUE` is repeatable and sets free-form session
flags for plugins; if you repeat a key, the last value wins. The meltdown works with `--play` and after a normal show, and
`--then` is unaffected. The app plays normally, breaks by itself a few seconds
in (she says something cursed, regions go red, the chart crashes, the hack gets
traced), and then everything melts down: the frozen frame's characters
glitch-decay into red noise, an error cascade scrolls, a fake death screen
appears (a `137` exit, a kernel panic, or a blue screen), and a "jk" reveal
follows. Esc during the meltdown skips ahead; esc before the app breaks just exits
cleanly with the app's normal goodbye. `--auto` does not cut a failing app
short, and a failing call picks up by itself after two seconds of ringing.


### Grid and spotlight

`--grid COLSxROWS` shows exactly that many feeds (`--grid 3x2` is six). With no
`-n`, that many agents run. With more agents than cells (`larp --grid 3x2 -n 20`),
a spotlight rotates through them: a feed stays on screen for at least two
seconds, then the agent that has waited longest takes its place (ties go to the
busiest). Swaps are staggered one cell at a time. The header still counts every
agent.

### Writing your own pack

What the agents say and do comes from a Tracery-style grammar in a TOML pack
file. Built-in packs live in `src/agentic_larp/packs/`; yours go in
`~/.config/agentic-larp/packs/` (or `$XDG_CONFIG_HOME/agentic-larp/packs/`),
where every `*.toml` is loaded at startup (a broken one prints a warning and is
skipped), or anywhere with `--pack FILE` (repeatable; a broken one is an
error). Later packs replace earlier ones with the same key: built-ins, then the
config directory, then `--pack`. `larp --list` shows them all, and repeating
`-s` deals agents round-robin across the chosen packs.
Without `-s`, the pack whose `keywords` match the most distinct whole words in
your task wins (ties go to the earlier pack), and no match means `generic`.

```toml
[pack]
key = "zebra"                 # required: the name for -s
task = "build me a zebra"     # required: shown in the header
keywords = ["zebra", "stripes"]  # optional: a task containing one picks this pack
app = "stonks"                # optional: launched after shipping (default deploy)

[areas]                       # required: one agent per area, dealt in order
stripes = ["stripes.py", "pattern.py"]

[areas.herd]                  # or a table, with rules for that area only
files = ["herd.py"]
rules = { quip = ["Herd assembled."] }

[rules]                       # optional: replaces same-named rules in the base
word = ["stripe", "mane", "hoof"]
quip = ["Stripes are black. Probably.", { text = "Rare quip.", weight = 0.2 }]
final = ["Zebra shipped."]
code = ["#word# = #n#", "import #word#"]
command = ["pytest -q", "make zebra"]
```

A rule is a string, or a list of alternatives; each alternative is a string or
a `{ text = "...", weight = 2 }` table (default weight 1, must be positive).
Text refers to other rules as `#name#`, optionally with modifiers applied left
to right: `#word.capitalize#` (`Red_flags`), `#word.camel#` (`RedFlags`),
`#word.upper#`. A lone `#` is just a `#`. These names are bound by the
simulation and need no rule: `file`, `area`, `agent`, `intern`, `n`. A pack must
end up with the rules `action`, `quip`, `final`, `intern_task`, and `todo`
(one line of an agent's todo list, such as `Write tests for #file#`; it is
required now, so a custom base grammar must define it too); the base
grammar supplies them and the machinery behind them (edits, shell runs that
fail and recover, reads, writes, greps, web searches, delegation to interns),
so a pack mostly provides vocabulary: `word`, `code`, `command`, `quip`,
`final`, and optionally its own `todo` lines.

An `action` expands to a script with one tagged line per row:

| Tag | Shows |
| --- | --- |
| `tool: Name(argument)` | a tool call such as `Edit(face.cpp)` |
| `add: code` / `del: code` | a green or red diff line, numbered in order |
| `ok:` / `fail:` / `note:` | a result line in green, red, or dim |
| `say:` | a line of agent chatter |

### Toolchains and pack inheritance

A pack can build on others. `extends = "cpp"` (or `["a", "b"]`) in `[pack]`
layers the parents' rules under its own. With several parents, a later
parent's whole rule (including anything it `[extend]`ed) replaces an earlier
parent's rule of the same name; to keep both, combine them with `[extend]` in
the child. The pack's own `[rules]` win over all parents. A new `[extend]` table takes
the same shapes as `[rules]` but appends alternatives to the rule resolved so
far (the base's, a parent's, or one from your own `[rules]`), creating it if it
doesn't exist. A concrete pack with no `task`, `[areas]` or `app` inherits them
from its last parent that has them; `keywords` are never inherited.

`abstract = true` marks a pack that exists only to be extended; its `task`,
`[areas]`, `keywords` and `app` are all optional. The built-in toolchains
(`cpp`, `typescript`, `python`, `rust`) are abstract packs with real build and
test commands, listed under "toolchains" in `larp --list`. `-s cpp` explains
that it is abstract. Your own packs in the config directory can extend them,
and each other, in any file order (cycles are an error). `--pack` files are
loaded in argument order, so list parents first:

```toml
[pack]
key = "game"
extends = ["cpp"]
task = "build a game engine"

[areas]
render = ["render.cpp", "shaders.glsl"]

[extend]
quip = ["60 fps (on my machine)."]
```

### Work phases

What an agent does is split into phases: `explore`, `implement`, `build`,
`test` and `debug`, plus `anytime` odds and ends (git status, a quick read,
delegation). The base grammar's `action` chooses among them, and packs and
toolchains can override any phase rule (for example `build_command`,
`test_command` and `build_result`). `--policy phased` walks the phases in a
realistic rhythm: explore leads to implement, implement to build or test,
build and test sometimes lead on to debug (the policy doesn't know whether a
run failed), mostly implementing, with `anytime` actions sprinkled in.

#### Upgrading packs

The base grammar's old `bash` and `shell` rules are gone: use `build_command`,
`test_command` and `command` instead. The phase rule names (`explore`,
`implement`, `build`, `test`, `debug` and `anytime`) are reserved by the base;
a pack that defines a rule with one of those names replaces that phase.

### Choice policies

When a rule has several alternatives, a policy decides which one is used.
`--policy NAME` selects it (`larp --list` shows the names). Each lead agent and
each intern gets its own policy instance.

| Policy | Behavior |
| --- | --- |
| `random` (default) | weighted random, no memory |
| `phased` | walks the work phases (explore, implement, build, test, debug) in a realistic rhythm; varied for other rules |
| `varied` | never repeats a rule's previous pick, and shies away from older ones (still follows weights) |

A policy is any object with `choose(symbol, alternatives, rng) -> int`, where
`alternatives` is the rule's `(text, weight)` pairs and the result is the index
to use. It may keep state. Register a class or factory under the
`agentic_larp.policies` entry-point group:

```python
import random
from collections.abc import Sequence


class Heaviest:
    def choose(
        self,
        symbol: str,
        alternatives: Sequence[tuple[str, float]],
        rng: random.Random,
    ) -> int:
        return max(range(len(alternatives)), key=lambda i: alternatives[i][1])
```

```toml
[project.entry-points."agentic_larp.policies"]
heaviest = "my_package.policies:Heaviest"
```

Then run `larp --policy heaviest`. A plugin that fails to load prints a
warning and is skipped; choosing something that is not a policy is a usage
error.

### Events

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
| `Report` | `who`, `text` | a line for the report feed (`sim.report(who, text)`) |

### Widgets

The wall has four regions: `header`, `swarm`, `footer` and `panel` (one per
agent). A full-width region is a `Widget`, with `height(width, available) ->
int` (rows wanted; 0 hides it) and `render(width)`. The `panel` region is a
`PanelWidget`, with `render(agent)`. Each is built once from a factory that
takes the `Wall`, so it can subscribe to `wall.sim.events`. Register a class or
function under the `agentic_larp.widgets` entry-point group, named after the
region it replaces; the rest stay built in.

```toml
[project.entry-points."agentic_larp.widgets"]
footer = "my_package.widgets:Footer"
```

`Wall(sim, console, widgets={"footer": Footer})` does the same in code. A
widget plugin that fails to load, or is named after an unknown region, stops
the show with an error, like stage and app plugins.

### Writing your own app

An app is a function that takes an `AppContext`. The usual shape is a screen
object with `render`, `on_key`, and `tick`, driven by `run_loop`:

```python
from rich.text import Text

from agentic_larp.apps import AppContext, run_loop


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
```

Register it in your package's `pyproject.toml`:

```toml
[project.entry-points."agentic_larp.apps"]
counter = "my_package.counter:run"
```

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

### FAQ

**Does it call any AI?** No. No network, no API keys, no tokens. The token
counter is lying.

**Is the cost real?** It's as real as your agents' productivity.

**Is this affiliated with any AI company?** No. It's a parody.

## Development

Requires [uv](https://docs.astral.sh/uv/).

```console
uv sync                    # create .venv and install the package in editable mode
uv run pre-commit install  # install the git hooks
uv run nox                 # run every check
uv run larp                # try it
```

| Session | What it does |
| --- | --- |
| `lint` | `ruff format --check` and `ruff check` |
| `typecheck` | `ty check` against every supported Python version |
| `tests` | pytest with pytest-xdist and coverage on Python 3.11–3.15 |
| `coverage` | combines coverage, writes `htmlcov/`, fails under 90% |
| `build` | `uv build` into `dist/` |
| `bump` | `nox -s bump -- major\|minor\|patch` |

Pass arguments through to pytest with `uv run nox -s tests-3.11 -- -k name`.

The full-screen loops are tested with a fake clock (`tests/conftest.py`) and
scripted keystrokes (`tests/support.py`), so a 90-second deploy runs in
milliseconds.

### Layout

```text
src/agentic_larp/
├── __init__.py      # public API, re-exported from the private modules
├── _cli.py          # the larp command
├── _errors.py       # LarpError, GrammarError
├── _grammar.py      # grammars and activity scripts
├── _grid.py         # the --grid spec
├── _log.py          # LogLine
├── _packs.py        # pack loading and discovery
├── packs/           # built-in packs (TOML) and the base grammar
├── _keys.py         # non-blocking keyboard input (POSIX and Windows)
├── _scenarios.py    # picking and generating scenarios
├── _sim.py          # the fake agents
├── _flow.py         # Session, Stage, run_flow: the pluggable stage pipeline
├── _stages.py       # the built-in stages (work, wrap, ready, ship, ...)
├── _wall.py         # the agent wall screen
├── meltdown.py      # public meltdown library (impl in _meltdown.py)
└── apps/            # payoff apps; AppContext, Screen, run_loop are public
```

### Branches

`main` holds releases only. `dev` accumulates feature pull requests, which are
squash-merged. Feature work happens on `dev-<name>` branches cut from `dev`,
and pull requests target `dev`. On GitHub, make `dev` the default branch so
pull requests target it, allow only squash merges into it, and protect
`main`.

### Working with Claude Code

`CLAUDE.md` is the entry point: commands, the definition of done, and how work
is delegated across model tiers. `.claude/` holds the rules that load per file
type, the subagents, the skills (`/plan`, `/feature`, `/fix-gate`, `/release`),
the hooks, and the permission allowlist. All of it is committed, so every
contributor's agent behaves the same. `/marathon` runs a multi-hour plan
with a commit per step and pauses when the subscription usage window nears
its limit. Personal overrides go in `CLAUDE.local.md` and
`.claude/settings.local.json`, both gitignored.

## Releasing

From `dev`, with a clean tree and nothing on `main` that `dev` lacks:

```console
uv run nox -s bump -- minor
uv run nox
git commit -am "chore(release): v$(uv version --short)"
git switch main && git merge --ff-only dev
git tag -a "v$(uv version --short)" -m "v$(uv version --short)"
git switch dev
git push origin dev main --follow-tags
```

The tag is annotated because `--follow-tags` pushes only annotated tags.
Pushing it runs `.github/workflows/release.yml`, which checks that the tag is
on `main` and matches the project version, then publishes to PyPI through
trusted publishing. `/release` runs these steps.

## License

MIT. See [LICENSE](LICENSE).

## AI disclosure

All of the code in this repository is generated with
[Claude Code](https://claude.com/claude-code), working under the direction of
Christopher Priebe. Every commit credits Claude as a co-author. Every change
still passes the same gate (lint, type check, tests on every supported Python,
coverage), and any defect is the maintainer's to fix.
