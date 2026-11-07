import io
from dataclasses import dataclass, field

from rich.console import Console

MIN_SLEEP = 0.001


@dataclass
class FakeClock:
    """Stands in for time.monotonic/time.sleep so loops run instantly."""

    now: float = 0.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += max(seconds, MIN_SLEEP)


@dataclass
class ScriptedKeys:
    """A key source that releases each key once the fake clock reaches its time."""

    clock: FakeClock
    schedule: list[tuple[float, str]] = field(default_factory=list)

    def read(self) -> list[str]:
        due = [key for at, key in self.schedule if at <= self.clock.now]
        self.schedule = [(at, key) for at, key in self.schedule if at > self.clock.now]
        return due


def output(console: Console) -> str:
    file = console.file
    assert isinstance(file, io.StringIO)
    return file.getvalue()
