# Running the show

How a run behaves in detail: the keys, the plan, timing, the payoff apps,
failing on purpose and the grid. Back to the [README](../README.md).

## Keys

| You do | It does |
| --- | --- |
| type `ship it` ⏎ | every agent wraps up and reports done |
| type `ship it` again (or ⏎) | `git push --force`, then the payoff app launches |
| type anything else ⏎ | the orchestrator "routes" it; the agents are on it |
| type `spawn` ⏎ | one more agent joins (only while the agents are still running) |
| esc | dismiss the agents |

While an agent is asking a question (see [Questions](packs.md#questions)), the keys
are the question's: `1` to `4` answer, `↑`/`↓` and ⏎ pick, and esc takes the
recommendation, like everyone does. Typing, `ship it` and quitting wait until
it is answered.

The prompt at the bottom is you messaging the orchestrator, the lead agent
named in the header. The clock in the header always runs in real time, and it
stops once every agent is done.

## Options and timing

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

## The hacker app

The hacker app plays four stages by itself (SCANNING, DUMPING MEMORY, CRACKING
PASSWORD, TRACING) and ends on a flashing ACCESS GRANTED after roughly 25
seconds. Every keypress pushes it forward, so mashing keys finishes sooner. Tab
flashes ACCESS GRANTED at any time and esc logs off. When failing, the hack
never promises access: tab flashes ACCESS DENIED and the footer says
`tab: access denied`.

## Failing on purpose

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

## Grid and spotlight

`--grid COLSxROWS` shows exactly that many feeds (`--grid 3x2` is six). With no
`-n`, that many agents run. With more agents than cells (`larp --grid 3x2 -n 20`),
a spotlight rotates through them: a feed stays on screen for at least two
seconds, then the agent that has waited longest takes its place (ties go to the
busiest). Swaps are staggered one cell at a time. The header still counts every
agent.
