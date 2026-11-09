# Contributing

Thanks for wanting to make the fake agents more convincing. Back to the
[README](README.md).

## Setup

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

`.github/workflows/ci.yml` runs the same sessions at release time only: on the
release pull request into `main`, and from the release workflow before it
publishes. It runs lint and type check, the tests on each Python in parallel,
then coverage combined across them. Work on `dev` is gated locally with
`uv run nox`; run CI by hand from the Actions tab when you want it.

## Branches

`main` holds releases only. `dev` accumulates feature pull requests, which are
squash-merged. Feature work happens on `dev-<name>` branches cut from `dev`,
and pull requests target `dev`. On GitHub, make `dev` the default branch so
pull requests target it, allow only squash merges into it, and protect
`main`.

Commits follow [Conventional Commits](https://www.conventionalcommits.org/)
(`feat:`, `fix:`, `docs:`, ...), with a body that says why.

## The demo GIF

The demo GIF at the top of the README is scripted in `assets/demo.tape`.
Re-record it from the repository root with [vhs](https://github.com/charmbracelet/vhs)
(`vhs assets/demo.tape`); it runs a fixed seed, so the take is repeatable.
The committed GIF is then shrunk to about 5 MB with ffmpeg:

```bash
ffmpeg -i assets/demo.gif -vf "fps=10,split[a][b];[a]palettegen=max_colors=48:stats_mode=diff[p];[b][p]paletteuse=dither=none:diff_mode=rectangle" demo-small.gif && mv demo-small.gif assets/demo.gif
```

The full-screen loops are tested with a fake clock (`tests/conftest.py`) and
scripted keystrokes (`tests/support.py`), so a 90-second deploy runs in
milliseconds.

## Layout

```text
src/agentic_larp/
├── __init__.py      # tiny root: main, LarpError, GrammarError, __version__
├── cli.py sim.py events.py stages.py widgets.py packs.py policies.py keys.py
│                    # public modules, re-exporting from the private ones
├── plugins.py       # public plugin loader (impl in _plugins.py)
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
└── apps/            # payoff apps: one module per app, each defining APP
```

## Working with Claude Code

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
# in CHANGELOG.md, rename "Unreleased" to the new version and date it
uv run nox
git commit -am "chore(release): v$(uv version --short)"
git switch main && git merge --ff-only dev
git tag -a "v$(uv version --short)" -m "v$(uv version --short)"
git switch dev
git push origin dev main --follow-tags
```

The tag is annotated because `--follow-tags` pushes only annotated tags.
Pushing it runs `.github/workflows/release.yml`, which checks that the tag is
on `main` and matches the project version, runs the CI gate on the tagged
commit, then publishes to PyPI through trusted publishing. `/release` runs
these steps.
