# Changelog

All notable changes to agentic-larp. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/). Before 1.0, a minor release may
change the public API; the "Stable surface" section of the README says what
plugins can rely on.

## [Unreleased]

## [0.1.0] - 2026-11-09

The first release. Everything below is new.

### The show

- `larp`: a terminal UI where a swarm of fake lead agents and interns "build"
  your app from a todo plan, then ship it. Runs converge on their own or, with
  the endless mode, creep in scope forever.
- Agents stop mid-run to ask questions; your answers add todos, spawn agents,
  or set the ending.
- A configurable grid of agent panels with a rotating spotlight that brings the least recently shown agent in.
- Eleven payoff apps launch after shipping: deploy, call, hacker, stonks,
  dropship, memecoin, wrapper, nft, thoughtleader, clipfarm and matchmaker.
  Any of them can fail on purpose and end in a shared meltdown.

### Content

- Grammar-driven scenario packs in TOML, with inheritance and toolchain packs
  for C++, Python, Rust and TypeScript.
- Random, varied and phased choice policies for grammar expansion.

### Extending (the 0.1 API)

- Public submodules, each with an explicit `__all__`: `cli`, `sim`, `events`,
  `stages`, `widgets`, `packs`, `policies`, `apps`, `meltdown`, `keys`,
  `questions` and `plugins`. The root exports only `main`, the errors and
  `__version__`.
- One entry-point plugin registry for stages, widgets, policies and apps.
- An event bus on every sim, and pluggable wall widgets.
- Plugins see agents and interns through the read-only `AgentView` and
  `InternView` protocols. `SwarmSettings.log_length` sets how many lines each
  panel log keeps.

### Notes

- `Wall.handle_key("esc")` returns `None`; escape and quit go through
  `ScreenStage.on_escape`/`on_quit`.

### Project

- CI runs the nox gate (lint, type check, tests on Python 3.11 to 3.15,
  coverage) on release pull requests into `main` and before publishing; the
  release workflow publishes to PyPI only after that gate passes.
