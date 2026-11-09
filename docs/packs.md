# Writing packs

How to write your own scenario, branch the run with questions, build on the
toolchain packs, and choose how lines are picked. Back to the
[README](../README.md).

## Your first pack

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
required, so a custom base grammar must define it too); the base
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

## Questions

An agent can pause mid-run and ask you something, Claude Code style. Its
panel stops (no tokens, calls or todo progress) until you answer; the others
keep going and the swarm cannot converge without it. Declare them in a pack
with `[[questions]]` and nested `[[questions.options]]`:

```toml
[[questions]]
key = "friday"                     # names it; a child pack's question with the same key replaces it
prompt = "Deploy to prod on a Friday?"
at = 0.2                           # when, as a fraction of --length (0 to 1, default 0.5)
recommended = 0                    # option index the cursor starts on; esc and demo mode take it
when = { ending = "success" }      # only asked if every flag matches (optional)
[[questions.options]]
label = "Ship it"                  # 2 to 4 options, unique labels
description = "what could go wrong"
sets = { ending = "meltdown" }     # session flags this answer sets
todos = 2                          # 0 to 5 extra todos for the asking agent
spawn = 1                          # 0 to 3 agents to spawn
[[questions.options]]
label = "Wait until Monday"
sets = { ending = "success" }
```

Each question is asked once, at the first update after its time, by a random
running agent, one at a time. Answers set flags (`ending = "meltdown"` makes
the payoff app break), so later questions can branch with `when`. Children
replace inherited questions by `key`, in the parent's position; new keys are
appended. Questions are asked with `--forever` too. `at` is a fraction of
`--length`; a value near 1 may never come before the swarm converges, and then
the question is never asked. Keys are ignored for 0.4 seconds after a
question opens (so typing does not answer it). While one is open, only `1` to
`4`, the arrows, enter and esc do anything; calling `sim.ship()` from code
answers it with its recommendation. In demo mode (`--auto`) the recommendation
is taken after 2.5 seconds of sim time, and auto-ship waits until the question
is answered. Flags pinned with `--flag` are never changed: a question whose
options set a pinned flag is skipped, so `--flag ending=success -s prod
--auto 8` never melts down. `Sim.length` is read-only.

## Toolchains and pack inheritance

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

## Work phases

What an agent does is split into phases: `explore`, `implement`, `build`,
`test` and `debug`, plus `anytime` odds and ends (git status, a quick read,
delegation). The base grammar's `action` chooses among them, and packs and
toolchains can override any phase rule (for example `build_command`,
`test_command` and `build_result`). `--policy phased` walks the phases in a
realistic rhythm: explore leads to implement, implement to build or test,
build and test sometimes lead on to debug (the policy doesn't know whether a
run failed), mostly implementing, with `anytime` actions sprinkled in.

### Upgrading packs

The base grammar's old `bash` and `shell` rules are gone: use `build_command`,
`test_command` and `command` instead. The phase rule names (`explore`,
`implement`, `build`, `test`, `debug` and `anytime`) are reserved by the base;
a pack that defines a rule with one of those names replaces that phase.

## Choice policies

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
