import io
from dataclasses import dataclass, field

from rich.console import Console

MIN_SLEEP = 0.001
CLOCK_LIMIT = 600.0  # simulated seconds; turns a hung loop into a failure


@dataclass
class FakeClock:
    """Stands in for time.monotonic/time.sleep so loops run instantly."""

    now: float = 0.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += max(seconds, MIN_SLEEP)
        if self.now > CLOCK_LIMIT:
            message = f"fake clock passed {CLOCK_LIMIT:.0f}s: a loop never ended"
            raise RuntimeError(message)


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
