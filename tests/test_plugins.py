import importlib.metadata
import random
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest
from rich.console import Console, RenderableType
from rich.text import Text

from agentic_larp import LarpError, main
from agentic_larp.apps import (
    APP_ENTRY_POINT_GROUP,
    App,
    AppContext,
    app_registry,
    discover_apps,
)
from agentic_larp.packs import pick_scenario
from agentic_larp.plugins import load_registry
from agentic_larp.sim import Sim, SwarmSettings
from agentic_larp.stages import STAGE_ENTRY_POINT_GROUP, Session, run_flow
from agentic_larp.widgets import WIDGET_ENTRY_POINT_GROUP
from support import FakeClock

GROUP = "agentic_larp.testing"
BUILTIN_APPS = {
    "call",
    "hacker",
    "deploy",
    "stonks",
    "dropship",
    "memecoin",
    "wrapper",
    "nft",
    "thoughtleader",
    "clipfarm",
    "matchmaker",
}


@dataclass
class FakeEntryPoint:
    name: str
    target: object

    def load(self) -> object:
        return self.target


@dataclass
class BrokenEntryPoint:
    name: str

    def load(self) -> object:
        message = f"{self.name} is broken"
        raise ImportError(message)


def fake_plugins(
    monkeypatch: pytest.MonkeyPatch, groups: dict[str, list[object]]
) -> None:
    real = importlib.metadata.entry_points

    def fake_entry_points(*, group: str) -> object:
        if group in groups:
            return groups[group]
        return real(group=group)

    monkeypatch.setattr(importlib.metadata, "entry_points", fake_entry_points)


def as_int(name: str, value: object) -> int:
    if not isinstance(value, int):
        message = f"{name} is not a number"
        raise TypeError(message)
    return value


def test_builtins_come_first_and_plugins_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_plugins(
        monkeypatch, {GROUP: [FakeEntryPoint("two", 22), FakeEntryPoint("three", 3)]}
    )
    assert load_registry(GROUP, {"one": 1, "two": 2}) == {
        "one": 1,
        "two": 22,
        "three": 3,
    }


def test_broken_and_rejected_plugins_go_to_on_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_plugins(
        monkeypatch,
        {
            GROUP: [
                BrokenEntryPoint("broken"),
                FakeEntryPoint("wrong", "not a number"),
                FakeEntryPoint("fine", 7),
            ]
        },
    )
    errors: list[tuple[str, Exception]] = []
    registry = load_registry(
        GROUP,
        {"one": 1},
        check=as_int,
        on_error=lambda name, err: errors.append((name, err)),
    )
    assert registry == {"one": 1, "fine": 7}
    assert [name for name, _ in errors] == ["broken", "wrong"]
    assert isinstance(errors[0][1], ImportError)


def test_without_on_error_a_broken_plugin_is_a_larp_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_plugins(monkeypatch, {GROUP: [BrokenEntryPoint("broken")]})
    with pytest.raises(LarpError, match=r"agentic_larp\.testing.*'broken'"):
        load_registry(GROUP, {})


def test_every_builtin_app_describes_itself() -> None:
    apps = discover_apps()
    assert set(apps) == BUILTIN_APPS
    for name, app in apps.items():
        assert isinstance(app, App)
        assert app.name == name
        assert app.description.strip()
        assert callable(app.run)
    assert app_registry().keys() >= BUILTIN_APPS


def forget_package(monkeypatch: pytest.MonkeyPatch, package: str) -> None:
    """Make sure the package and its modules are imported fresh, and dropped after."""
    for name in [*sys.modules]:
        if name == package or name.startswith(f"{package}."):
            monkeypatch.delitem(sys.modules, name)


def make_package(root: Path, name: str, modules: dict[str, str]) -> None:
    package = root / name
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    for module, source in modules.items():
        (package / f"{module}.py").write_text(source, encoding="utf-8")


def app_source(name: str) -> str:
    return (
        "from agentic_larp.apps import App\n\n"
        f"APP = App({name!r}, 'an app', lambda context: None)\n"
    )


def test_two_modules_claiming_one_app_name_is_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    make_package(
        tmp_path, "twin_apps", {"_a": app_source("twin"), "_b": app_source("twin")}
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    forget_package(monkeypatch, "twin_apps")
    with pytest.raises(LarpError, match=r"'twin'.*twin_apps\._a.*twin_apps\._b"):
        discover_apps("twin_apps")


def test_discovering_apps_in_a_plain_module_is_an_error() -> None:
    with pytest.raises(
        LarpError, match=re.escape("'agentic_larp.apps._base' is not a package")
    ):
        discover_apps("agentic_larp.apps._base")


def test_discovered_apps_are_listed_by_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    make_package(
        tmp_path,
        "sorted_apps",
        {"_a": app_source("zebra"), "_b": app_source("aardvark")},
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    forget_package(monkeypatch, "sorted_apps")
    assert list(discover_apps("sorted_apps")) == ["aardvark", "zebra"]
    assert list(discover_apps()) == sorted(BUILTIN_APPS)


def test_an_app_is_one_new_module(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package = tmp_path / "more_apps"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "_kazoo.py").write_text(
        "from agentic_larp.apps import App\n\n"
        "def run(context):\n"
        "    context.console.print('KAZOO')\n\n"
        "APP = App('kazoo', 'plays the kazoo', run)\n",
        encoding="utf-8",
    )
    (package / "_helpers.py").write_text("VALUE = 1\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    forget_package(monkeypatch, "more_apps")
    apps = discover_apps("more_apps")
    assert set(apps) == {"kazoo"}
    assert apps["kazoo"].description == "plays the kazoo"


def test_an_app_can_be_called_like_a_function(
    console: Console, clock: FakeClock
) -> None:
    app_registry()["stonks"](AppContext(console=console, task="t", auto=1.0, fps=10))
    assert clock.now > 1.0


def bare(context: AppContext) -> None:
    """A plugin app that is just a function."""
    context.console.print("BARE APP RAN")


def test_plugin_apps_can_be_functions_or_apps(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fancy = App("fancy", "a very fancy plugin", bare)
    fake_plugins(
        monkeypatch,
        {
            APP_ENTRY_POINT_GROUP: [
                FakeEntryPoint("bare", bare),
                FakeEntryPoint("fancy", fancy),
            ]
        },
    )
    apps = app_registry()
    assert apps["bare"].name == "bare"
    assert apps["bare"].description == "plugin"
    assert apps["fancy"] is fancy
    assert main(["--list"]) == 0
    listing = capsys.readouterr().out
    assert "a very fancy plugin" in listing
    assert main(["--play", "bare"]) == 0
    assert "BARE APP RAN" in capsys.readouterr().out


class Loud:
    def height(self, width: int, available: int) -> int:
        return 1 if width and available else 0

    def render(self, width: int) -> RenderableType:
        return Text("x" * min(width, 1))


@pytest.mark.parametrize(
    "group", [APP_ENTRY_POINT_GROUP, STAGE_ENTRY_POINT_GROUP, WIDGET_ENTRY_POINT_GROUP]
)
def test_a_broken_plugin_of_any_kind_only_warns(
    group: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    clock: FakeClock,
) -> None:
    fake_plugins(monkeypatch, {group: [BrokenEntryPoint("busted")]})
    assert main(["--list"]) == 0
    listing = capsys.readouterr().out
    assert "warning" in listing
    assert "busted" in listing
    args = ["-s", "prod", "--auto", "1", "--length", "1", "--app", "none", "-i", "0"]
    assert main(args) == 0
    text = capsys.readouterr().out
    assert "✓ shipped" in text
    assert "busted" in text
    assert clock.now > 1.0


def test_a_widget_plugin_for_an_unknown_region_only_warns(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    clock: FakeClock,
) -> None:
    def factory(_wall: object) -> Loud:
        return Loud()

    fake_plugins(
        monkeypatch, {WIDGET_ENTRY_POINT_GROUP: [FakeEntryPoint("sidebar", factory)]}
    )
    args = ["-s", "prod", "--auto", "1", "--length", "1", "--app", "none", "-i", "0"]
    assert main(args) == 0
    text = capsys.readouterr().out
    assert "✓ shipped" in text
    assert "sidebar" in text
    assert clock.now > 1.0


def test_a_session_routes_plugin_errors_to_its_own_callback(
    monkeypatch: pytest.MonkeyPatch, console: Console, clock: FakeClock
) -> None:
    fake_plugins(
        monkeypatch,
        {
            STAGE_ENTRY_POINT_GROUP: [BrokenEntryPoint("bad_stage")],
            WIDGET_ENTRY_POINT_GROUP: [BrokenEntryPoint("bad_widget")],
            APP_ENTRY_POINT_GROUP: [BrokenEntryPoint("bad_app")],
        },
    )
    errors: list[str] = []
    settings = SwarmSettings(agents=2, interns=0, length=1.0)
    sim = Sim([pick_scenario(None, "prod")], settings, random.Random(1))
    session = Session(
        console=console,
        task=sim.task,
        sim=sim,
        rng=random.Random(1),
        auto=1.0,
        app="stonks",
        on_error=lambda name, _err: errors.append(name),
    )
    assert run_flow(session) == 0
    assert set(errors) == {"bad_stage", "bad_widget", "bad_app"}
    assert clock.now > 1.0


def test_a_stage_plugin_that_is_not_a_stage_only_warns(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    clock: FakeClock,
) -> None:
    fake_plugins(monkeypatch, {STAGE_ENTRY_POINT_GROUP: [FakeEntryPoint("review", 42)]})
    args = ["-s", "prod", "--auto", "1", "--length", "1", "--app", "none", "-i", "0"]
    assert main(args) == 0
    text = capsys.readouterr().out
    assert "warning: review" in text
    assert "✓ shipped" in text
    assert clock.now > 1.0


def test_widget_warnings_name_the_plugin_once(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def factory(_wall: object) -> Loud:
        return Loud()

    fake_plugins(
        monkeypatch, {WIDGET_ENTRY_POINT_GROUP: [FakeEntryPoint("sidebar", factory)]}
    )
    assert main(["--list"]) == 0
    warning = next(
        line for line in capsys.readouterr().out.splitlines() if "warning" in line
    )
    assert warning.count("sidebar") == 1
