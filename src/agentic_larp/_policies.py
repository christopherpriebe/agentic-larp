"""Policies that choose which alternative a grammar rule expands to."""

import importlib.metadata
import random
from collections import deque
from collections.abc import Callable, Sequence
from typing import Protocol

POLICY_ENTRY_POINT_GROUP = "agentic_larp.policies"
_DEFAULT_MEMORY = 3
_DEFAULT_PENALTY = 0.15
_SECOND_MOST_RECENT = 2


class ChoicePolicy(Protocol):
    """Chooses one alternative of a rule each time it is expanded."""

    def choose(
        self,
        symbol: str,
        alternatives: Sequence[tuple[str, float]],
        rng: random.Random,
        /,
    ) -> int:
        """Pick an alternative.

        Args:
            symbol: The rule being expanded.
            alternatives: Its ``(text, weight)`` alternatives.
            rng: Random source.

        Returns:
            The index of the chosen alternative.
        """
        ...


class RandomPolicy:
    """Weighted random choice, with no memory."""

    def choose(
        self,
        _symbol: str,
        alternatives: Sequence[tuple[str, float]],
        rng: random.Random,
    ) -> int:
        """Pick an alternative at random, following the weights.

        Args:
            _symbol: The rule being expanded (unused).
            alternatives: Its ``(text, weight)`` alternatives.
            rng: Random source.

        Returns:
            The index of the chosen alternative.
        """
        weights = [weight for _, weight in alternatives]
        return rng.choices(range(len(alternatives)), weights)[0]


class VariedPolicy:
    """Weighted random choice that avoids repeating recent picks.

    The most recent pick of a rule is never chosen again straight away (unless
    the rule has one alternative). Older remembered picks are down-weighted by
    ``penalty ** (1 / (age - 1))``, so the second most recent is hit hardest.
    """

    def __init__(
        self, *, memory: int = _DEFAULT_MEMORY, penalty: float = _DEFAULT_PENALTY
    ) -> None:
        """Set how far back to remember and how hard to discourage repeats.

        Args:
            memory: How many recent picks of each rule to remember (at least 1).
            penalty: Weight multiplier for the second most recent pick, from
                0 (never) to 1 (no discouragement).

        Raises:
            ValueError: If ``memory`` is below 1 or ``penalty`` is outside 0 to 1.
        """
        if memory < 1:
            message = f"memory must be at least 1, not {memory}"
            raise ValueError(message)
        if not 0 <= penalty <= 1:
            message = f"penalty must be between 0 and 1, not {penalty}"
            raise ValueError(message)
        self.memory = memory
        self.penalty = penalty
        self._recent: dict[tuple[str, tuple[tuple[str, float], ...]], deque[int]] = {}

    def choose(
        self,
        symbol: str,
        alternatives: Sequence[tuple[str, float]],
        rng: random.Random,
    ) -> int:
        """Pick an alternative, steering away from recent picks.

        Args:
            symbol: The rule being expanded; memory is kept per distinct rule
                (its symbol and alternatives).
            alternatives: Its ``(text, weight)`` alternatives.
            rng: Random source.

        Returns:
            The index of the chosen alternative.
        """
        key = (symbol, tuple(alternatives))
        recent = self._recent.setdefault(key, deque(maxlen=self.memory))
        count = len(alternatives)
        original = [weight for _, weight in alternatives]
        weights = list(original)
        if count > 1 and recent:
            weights[recent[-1]] = 0.0
            penalized = list(weights)
            for age, index in enumerate(reversed(recent), start=1):
                if age >= _SECOND_MOST_RECENT:
                    factor = self.penalty ** (1 / (age - 1))
                    penalized[index] = min(penalized[index], weights[index] * factor)
            weights = penalized if sum(penalized) > 0 else weights
            if sum(weights) <= 0:
                weights = original
        choice = rng.choices(range(count), weights)[0]
        recent.append(choice)
        return choice


def policy_registry(
    on_error: Callable[[str, Exception], None] | None = None,
) -> dict[str, Callable[[], ChoicePolicy]]:
    """Return every policy factory by name: the built-ins, then plugins.

    Plugins register under the ``agentic_larp.policies`` entry-point group; the
    loaded value is a class or function that returns a policy.

    Args:
        on_error: Called with the plugin name and the error for each plugin
            that fails to load, which is then skipped. By default the error
            is raised.

    Returns:
        Policy name mapped to a zero-argument factory.
    """
    registry: dict[str, Callable[[], ChoicePolicy]] = {
        "random": RandomPolicy,
        "varied": VariedPolicy,
    }
    for entry_point in importlib.metadata.entry_points(group=POLICY_ENTRY_POINT_GROUP):
        try:
            registry[entry_point.name] = entry_point.load()
        except Exception as err:
            if on_error is None:
                raise
            on_error(entry_point.name, err)
    return registry
