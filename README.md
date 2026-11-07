# agentic-larp

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
larp --then "cmatrix"             # after shipping, run any real command
larp --play hacker                # skip the agents, go straight to an app
larp --auto 8                     # ships itself after 8s (for screen recordings)
larp --list                       # scenarios and apps
```

While it runs:

| You do | It does |
| --- | --- |
| mash any keys | agents get frantic (hacker typer, but for orchestration) |
| type `ship it` ⏎ | every agent wraps up and reports done |
| type `ship it` again (or ⏎) | `git push --force`, then the payoff app launches |
| type anything else ⏎ | the orchestrator "routes" it; the agents are on it |
| type `spawn` ⏎ | one more agent joins |
| esc | dismiss the agents |

Other options: `-n` sets the number of lead agents (default: whatever fits),
`-i` the number of interns (0 hides them), and `--speed` how fast everything
moves. Want different names on the panels? `--lead-model` and
`--intern-model` set them, for example `--lead-model fable --intern-model sonnet`.

When stdin is not a terminal (piped, in CI), `larp` ships itself after six
seconds.

### Scenarios and apps

| Scenario | The agents are "building" | After you ship |
| --- | --- | --- |
| `girlfriend` | `face.cpp`, `heart.hpp`, `ring.cpp` | **call**: she calls. Answer, and type to her. |
| `startup` | `Deck.tsx`, `valuation.ts`, `moat.ts` | **stonks**: your ticker, which only goes up |
| `hacker` | `exploit.c`, `payload.asm`, `proxy.go` | **hacker**: hacker typer; tab is ACCESS GRANTED |
| `prod` | `migrations/0042.sql`, `main.tf` | **deploy**: a global rollout; nobody gets paged |
| `generic` | whatever you typed | deploy or stonks |

The hacker typer types out agentic-larp's own source code, so it's technically
real code.

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
├── _keys.py         # non-blocking keyboard input (POSIX and Windows)
├── _scenarios.py    # scenario packs
├── _sim.py          # the fake agents
├── _theater.py      # the agent wall and the ship-it stages
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

Much of the code in this repository is generated by AI coding agents working
under the direction of Christopher Priebe, who reviews, tests, and takes full
responsibility for all of it. Every change passes the same gate regardless of
who wrote it, and any defect is the maintainer's to fix.
