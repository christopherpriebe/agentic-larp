"""The wall must keep drawing exactly what it drew before widgets existed.

The files under ``tests/golden/`` were rendered by the pre-widget wall on the
``dev`` branch (commit 3c68dc2) from the scenarios below. Spinner glyphs are
masked: dev derived each panel's spinner phase from ``hash(name)``, which
Python randomizes per process, so those characters never repeat across runs.
"""

import os
import random
import subprocess
import sys
from pathlib import Path

import pytest
from rich.console import Console

from agentic_larp import Grid, Sim, SwarmSettings, Wall, pick_scenario

HERE = Path(__file__).parent
GOLDEN = HERE / "golden"
SPINNER_GLYPHS = str.maketrans(dict.fromkeys("·✢✳✶✻✽", "*"))
DT = 0.05

# Each scenario is width, height, agents, interns, grid, then the wall's mode.
SCENARIOS: dict[str, tuple[int, int, int, int, Grid | None, str]] = {
    "tall-running": (140, 44, 6, 16, None, "running"),
    "short-running": (140, 30, 4, 16, None, "running"),
    "tiny-running": (80, 20, 2, 16, None, "running"),
    "no-interns": (140, 44, 6, 0, None, "running"),
    "grid-spotlight": (140, 44, 10, 8, Grid(2, 2), "running"),
    "tall-wrapping": (140, 44, 6, 16, None, "wrapping"),
    "tall-ready": (140, 44, 6, 16, None, "ready"),
    "tall-launching": (140, 44, 6, 16, None, "launching"),
}


def render(name: str) -> str:
    width, height, agents, interns, grid, mode = SCENARIOS[name]
    console = Console(
        width=width, height=height, force_terminal=True, color_system=None
    )
    settings = SwarmSettings(agents=agents, interns=interns, length=60.0)
    sim = Sim([pick_scenario(None, "prod")], settings, random.Random(11))
    wall = Wall(sim, console, grid=grid)
    for _ in range(int(3 / DT)):
        wall.step(DT)
    if mode != "running":
        sim.ship()
        wall.set_mode("wrapping")
        while mode != "wrapping" and not sim.is_all_done:
            wall.step(DT)
    if mode in {"ready", "launching"}:
        wall.set_mode("ready")
    if mode == "launching":
        wall.launch_lines = [
            ("● Bash(git push origin main --force)", "bold"),
            ("  ⎿  ✓ pushed (no one reviewed this)", "green"),
            ("● Bash(./deploy)", "bold"),
        ]
        wall.set_mode("launching")
        for _ in range(int(2 / DT)):
            wall.step(DT)
    with console.capture() as capture:
        console.print(wall.render(), height=height)
    return capture.get()


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_the_wall_renders_exactly_as_before(name: str) -> None:
    expected = (GOLDEN / f"wall-{name}.txt").read_text(encoding="utf-8")
    assert render(name).translate(SPINNER_GLYPHS) == expected.translate(SPINNER_GLYPHS)


def render_in_a_fresh_process(hash_seed: str) -> str:
    env = {**os.environ, "PYTHONHASHSEED": hash_seed}
    env["PYTHONPATH"] = os.pathsep.join(
        filter(None, [str(HERE), env.get("PYTHONPATH")])
    )
    code = "import test_wall_golden as g; print(g.render('tall-running'), end='')"
    result = subprocess.run(  # noqa: S603 - our own interpreter running a fixed snippet
        [sys.executable, "-c", code],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def test_spinners_are_the_same_in_every_process() -> None:
    assert render_in_a_fresh_process("1") == render_in_a_fresh_process("2")
