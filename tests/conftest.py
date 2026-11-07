import io
import time
from collections.abc import Callable
from pathlib import Path

import pytest
from rich.console import Console

from support import FakeClock, ScriptedKeys


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> FakeClock:
    fake = FakeClock()
    monkeypatch.setattr(time, "monotonic", fake.monotonic)
    monkeypatch.setattr(time, "sleep", fake.sleep)
    return fake


@pytest.fixture
def make_keys(clock: FakeClock) -> Callable[..., ScriptedKeys]:
    def make(*schedule: tuple[float, str]) -> ScriptedKeys:
        return ScriptedKeys(clock, list(schedule))

    return make


@pytest.fixture
def console() -> Console:
    return Console(
        file=io.StringIO(),
        width=140,
        height=44,
        force_terminal=True,
        color_system=None,
        legacy_windows=False,
    )


@pytest.fixture(autouse=True)
def config_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the pack config folder at an empty temp dir so no test reads the real one."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    packs = tmp_path / "config" / "agentic-larp" / "packs"
    packs.mkdir(parents=True)
    return packs
