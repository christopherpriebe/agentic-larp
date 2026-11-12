# agentic-larp

[![PyPI](https://img.shields.io/pypi/v/agentic-larp)](https://pypi.org/project/agentic-larp/)
[![Python](https://img.shields.io/pypi/pyversions/agentic-larp)](https://pypi.org/project/agentic-larp/)
[![CI](https://github.com/christopherpriebe/agentic-larp/actions/workflows/ci.yml/badge.svg)](https://github.com/christopherpriebe/agentic-larp/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/github/license/christopherpriebe/agentic-larp)](https://github.com/christopherpriebe/agentic-larp/blob/dev/LICENSE)

**Cosplay as a 10x AI engineer.**

![A swarm of fake agents builds "ship to prod on a friday", asks whether to
deploy on a Friday, ships it, and melts prod down. jk.](https://raw.githubusercontent.com/christopherpriebe/agentic-larp/dev/assets/demo.gif)

```bash
uvx agentic-larp
```

`larp` fills your terminal with a wall of AI agents editing files, running
tests, delegating to interns, and burning money in parallel. They make a plan,
ask you the hard questions ("Deploy to prod on a Friday?"), and converge on
something that is definitely production-ready. Then you type `ship it`, and
the thing they built launches.

None of it is real. Nothing is being built. There is no network, no API key,
and no model. The token counter is lying. The `$39.06` is imaginary. Your
coworkers walking past your desk do not need to know that.

> **This entire project is vibe coded.** Every line of code, test, and doc was
> generated with [Claude Code](https://claude.com/claude-code). A human typed
> `ship it`.

## Quickstart

```bash
uvx agentic-larp                     # run it once, no install
uv tool install agentic-larp         # or keep it around (pipx install works too)
larp "build me a girlfriend"         # then give the swarm a task
```

Needs Python 3.11+ and a terminal that can draw Unicode. Built on
[Rich](https://github.com/Textualize/rich).

Then, while it runs:

| You type | The swarm |
| --- | --- |
| `ship it` ⏎ | wraps up, and every agent reports done (`lgtm`, `yolo` and `deploy` work too) |
| `ship it` again, or ⏎ | `git push --force`, then the payoff app launches |
| `spawn` ⏎ | hires one more agent (while they are still working) |
| anything else ⏎ | the orchestrator "routes" it. The agents are on it. |
| `1`–`4`, `↑`/`↓` ⏎ | answers an agent's question; esc takes the recommendation, like everyone does |
| esc, or `q` ⏎ | dismisses the agents |

## What you get

- **A wall of agents.** Lead agents in panels with live tool calls (`Edit`,
  `Bash`, `Grep`, `WebSearch`), red/green diffs, failing builds that recover,
  token counters and a running bill, plus a strip of interns doing whatever
  interns do.
- **A plan first.** Every run opens with a `TodoWrite` screen; each agent works
  through 3 to 6 todos and the swarm converges in about `--length` seconds.
- **Agents that ask you things.** Mid-run, an agent pauses with a multiple-choice
  question. Your answer can add todos, spawn agents, or decide how the story
  ends.
- **Eleven payoff apps.** Ship, and you get a ringing phone, a stock that only
  goes up, a hacking montage, a memecoin launch, a viral thought-leadership post
  that writes itself, and more.
- **Failing on purpose.** Any app can break and melt down: glitching frames, an
  error cascade, a fake kernel panic or blue screen, and a "jk".
- **Endless mode.** `--forever`: the agents keep discovering scope creep and
  never finish. Very realistic.
- **Grids and spotlights.** `--grid 3x2` pins six feeds and rotates the rest of
  the swarm through them.
- **Your own content.** Scenarios are TOML grammar packs you can write, extend
  and share. Apps, widgets, stages and policies are Python plugins.

## Scenarios

Your task picks a scenario by its keywords (`larp "launch a memecoin"`), or you
force one with `-s`. Anything that matches nothing still works: `larp "uber for
cats"` puts the agents to work on `cats.ts` and `Uber.tsx`.

| Scenario | The agents are "building" | After you ship |
| --- | --- | --- |
| `girlfriend` | `face.cpp`, `heart.hpp`, `ring.cpp` | **call**: she calls. Answer, then pick replies with `1`-`3` or type freely. The swarm asks how much drama, how she texts, and whether to persist her. |
| `startup` | `Deck.tsx`, `valuation.ts`, `moat.ts` | **stonks**: your ticker, which only goes up |
| `hacker` | `exploit.c`, `payload.asm`, `proxy.go` | **hacker**: scan, dump memory, crack a password, outrun the trace (mash keys to go faster) |
| `prod` | `migrations/0042.sql`, `main.tf` | **deploy**: a global rollout; nobody gets paged |
| `dropship` | `products.json`, `checkout.liquid`, `meta_ads.py` | **dropship**: markups of 1,500%, shipping in 6-8 weeks |
| `memecoin` | `Token.sol`, `add_liquidity.ts`, `hype_bot.py` | **memecoin**: the liquidity is locked (trust me) |
| `wrapper` | `system_prompt.txt`, `llm_client.ts`, `pricing.ts` | **wrapper**: an AI startup racing its MRR against its API bill |
| `nft` | `ape_001.png.md`, `Collection.sol`, `ipfs_pin.ts` | **nft**: a pixel ape minting row by row; mind the floor |
| `thoughtleader` | `hook_v12_final.md`, `the_barista_story.md` | **thoughtleader**: a post that writes itself, one sentence per line. Agree? |
| `clipfarm` | `transcript_3h14m.txt`, `clip_912.mp4.md` | **clipfarm**: one 3-hour podcast becomes 912 vertical clips with one idea |
| `matchmaker` | `simulate_us.py`, `compatibility.py`, `expiry_timer.py` | **matchmaker**: the system assigns your match, and when it expires |
| `generic` | whatever you typed | deploy or stonks |

`larp --list` shows every scenario, app, toolchain and policy, including the
ones you add.

## Usage

```bash
larp                                # random scenario
larp "hack the mainframe"           # scenario picked from your task
larp -s hacker -s prod              # mix packs: agents alternate between them
larp --play hacker                  # skip the agents, go straight to the app
larp --grid 3x2 -n 20               # six feeds, a spotlight rotates through 20 agents
larp --length 40                    # converge in about 40s (default 20)
larp --forever                      # never converge: scope creep, forever
larp --flag ending=meltdown         # the payoff app breaks, then melts down (jk)
larp --then "cmatrix"               # after shipping, run any real command
larp --auto 8                       # ship by itself after 8s (for screen recordings)
larp --lead-model fable --intern-model sonnet   # pick the names on the panels
larp --pack ./zebra.toml -s zebra   # your own scenario pack
```

More knobs: `-n` lead agents (default: whatever fits your terminal), `-i`
interns (0 hides them), `--speed` how fast they work, `--policy` how they pick
their lines (`random`, `varied`, `phased`), `-a/--app` which app launches after
shipping, and `--seed` for reproducible nonsense. `larp --help` has them all.

When stdin is not a terminal (piped, in CI), `larp` ships itself after six
seconds of work, so it is safe to drop into a script. The plan's timing,
the meltdown, the spotlight and the hacker app's controls are covered in
**[Running the show](https://github.com/christopherpriebe/agentic-larp/blob/dev/docs/usage.md)**.

### The Friday question

The `prod` scenario's agent asks: *It's Friday, 4:55pm. Deploy to prod now?*
"Ship it" sets the ending to meltdown; "Wait until Monday" keeps prod alive.
Questions are plain TOML, so your packs can branch the run too:

```toml
[[questions]]
key = "friday"
prompt = "Deploy to prod on a Friday?"
at = 0.2                           # a fraction of --length
recommended = 0                    # what esc and --auto pick
[[questions.options]]
label = "Ship it"
sets = { ending = "meltdown" }     # answers set flags...
spawn = 1                          # ...and can hire agents or add todos
[[questions.options]]
label = "Wait until Monday"
sets = { ending = "success" }
```

Flags pinned on the command line always win: with `larp -s prod --flag
ending=success`, nobody even asks, and prod survives.

## Make it yours

**Write a scenario.** A pack is a Tracery-style grammar in TOML. Drop it in
`~/.config/agentic-larp/packs/` (or pass `--pack FILE`) and it shows up in
`larp --list`:

```toml
[pack]
key = "zebra"
task = "build me a zebra"
keywords = ["zebra", "stripes"]   # "larp build a zebra" picks this pack
extends = "python"                # real pytest/ruff commands from the toolchain
app = "stonks"

[areas]                           # one agent per area
stripes = ["stripes.py", "pattern.py"]

[rules]
word = ["stripe", "mane", "hoof"]
quip = ["Stripes are black. Probably.", "#word.capitalize# refactored."]
final = ["Zebra shipped."]
```

The base grammar does the heavy lifting (edits, builds that fail and recover,
greps, delegation to interns); your pack mostly brings vocabulary. Packs can
inherit from each other and from the `cpp`, `python`, `rust` and `typescript`
toolchains. The full reference is in **[Writing packs](https://github.com/christopherpriebe/agentic-larp/blob/dev/docs/packs.md)**.

**Write a plugin.** Apps, wall widgets, stages and choice policies are
entry-point plugins. A new payoff app is a screen with `render`, `on_key` and
`tick`, registered in your own package:

```toml
[project.entry-points."agentic_larp.apps"]
counter = "my_package.counter:APP"
```

Then `larp --play counter`. Plugins also get a typed event bus (`TodoDone`,
`QuestionAsked`, `ShipStarted`, ...) and a meltdown library so your app can
fail as spectacularly as the built-ins. See
**[Extending agentic-larp](https://github.com/christopherpriebe/agentic-larp/blob/dev/docs/extending.md)**.

### Stable surface

Before 1.0, a minor release may change the API. Plugins can rely on the read-only
`AgentView` and `InternView`, `SwarmSettings`, and the listed members of `Sim`
and `Wall`; the exact list is in
[Extending: Stable surface](https://github.com/christopherpriebe/agentic-larp/blob/dev/docs/extending.md#stable-surface).
Everything else may change between releases.

## FAQ

**Does it call any AI?** No. No network, no API keys, no tokens. The token
counter is lying.

**Is the cost real?** It's as real as your agents' productivity.

**Will it melt down my actual prod?** Only if you also pass
`--then "./deploy.sh"`. That one's on you.

**Is this affiliated with any AI company?** No. It's a parody. Inspired by
[programmergrind](https://www.tiktok.com/@programmergrind) on TikTok, whose
agent swarms ship faster than anyone's. Go watch them.

## Contributing

Packs, apps and jokes are all welcome. You need [uv](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/christopherpriebe/agentic-larp && cd agentic-larp
uv sync              # environment and editable install
uv run larp          # try it
uv run nox           # the full gate: lint, types, tests on 3.11-3.15, coverage
```

Branch from `dev` as `dev-<name>` and open your pull request against `dev`
(`main` only holds releases). Commits use
[Conventional Commits](https://www.conventionalcommits.org/). Setup details,
the release process, and how the demo GIF is recorded are in
[CONTRIBUTING.md](https://github.com/christopherpriebe/agentic-larp/blob/dev/CONTRIBUTING.md).
The [changelog](https://github.com/christopherpriebe/agentic-larp/blob/dev/CHANGELOG.md)
has what changed.

## License

MIT. See [LICENSE](https://github.com/christopherpriebe/agentic-larp/blob/dev/LICENSE).

## AI disclosure

All of the code in this repository is generated with
[Claude Code](https://claude.com/claude-code), working under the direction of
Christopher Priebe. Every commit credits Claude as a co-author. Every change
still passes the same gate (lint, type check, tests on every supported Python,
coverage), and any defect is the maintainer's to fix.
