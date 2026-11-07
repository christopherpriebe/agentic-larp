"""A typed event bus: the sim announces, widgets and plugins listen."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeVar, cast

if TYPE_CHECKING:
    from collections.abc import Callable

    from agentic_larp._log import LogLine
    from agentic_larp._sim import Agent, Todo

E = TypeVar("E", bound="Event")


@dataclass(frozen=True, slots=True)
class Event:
    """Base class for everything the sim announces."""


@dataclass(frozen=True, slots=True)
class AgentSpawned(Event):
    """A lead agent joined the swarm.

    Attributes:
        agent: The new agent.
    """

    agent: Agent


@dataclass(frozen=True, slots=True)
class LineShown(Event):
    """A line entered an agent's log.

    Attributes:
        agent: Whose log.
        line: The line.
    """

    agent: Agent
    line: LogLine


@dataclass(frozen=True, slots=True)
class TodoDone(Event):
    """An agent completed a todo.

    Attributes:
        agent: Who completed it.
        todo: The todo.
    """

    agent: Agent
    todo: Todo


@dataclass(frozen=True, slots=True)
class ScopeCreep(Event):
    """An agent found more work.

    Attributes:
        agent: Who found it.
        added: The todos appended to its list.
    """

    agent: Agent
    added: tuple[Todo, ...]


@dataclass(frozen=True, slots=True)
class AgentFinished(Event):
    """An agent wrapped up.

    Attributes:
        agent: The agent.
        final: Its closing remark.
    """

    agent: Agent
    final: str


@dataclass(frozen=True, slots=True)
class Converged(Event):
    """Every agent finished by completing its todos."""


@dataclass(frozen=True, slots=True)
class ShipStarted(Event):
    """The first "ship it" went out."""


@dataclass(frozen=True, slots=True)
class Report(Event):
    """A line for the report feed.

    Attributes:
        who: The speaker.
        text: What they said.
    """

    who: str
    text: str


class EventBus:
    """Delivers events to the handlers subscribed to their type."""

    def __init__(self) -> None:
        self._subscriptions: list[
            tuple[object, type[Event], Callable[[Event], None]]
        ] = []

    def subscribe(
        self, kind: type[E], handler: Callable[[E], None]
    ) -> Callable[[], None]:
        """Listen for events of a type, including its subclasses.

        Args:
            kind: The event class to match.
            handler: Called with each matching event.

        Returns:
            A function that cancels this subscription; calling it again does
            nothing, even if the same handler was subscribed twice.
        """
        token = object()
        entry = (token, kind, cast("Callable[[Event], None]", handler))
        self._subscriptions.append(entry)

        def unsubscribe() -> None:
            self._subscriptions[:] = [
                held for held in self._subscriptions if held[0] is not token
            ]

        return unsubscribe

    def publish(self, event: Event) -> None:
        """Deliver an event to its handlers, in subscription order.

        Delivery is to a snapshot taken when publishing starts, so a handler
        unsubscribed mid-publish still gets the current event.

        Args:
            event: What happened. A failing handler's exception propagates.
        """
        if not self._subscriptions:
            return
        for _token, kind, handler in tuple(self._subscriptions):
            if isinstance(event, kind):
                handler(event)
