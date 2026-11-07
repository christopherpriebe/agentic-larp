"""The one loader every plugin registry shares."""

import importlib.metadata
from collections.abc import Callable, Mapping
from typing import TypeVar

from agentic_larp._errors import LarpError

T = TypeVar("T")


def load_registry(
    group: str,
    builtins: Mapping[str, T],
    *,
    check: Callable[[str, object], T] | None = None,
    on_error: Callable[[str, Exception], None] | None = None,
) -> dict[str, T]:
    """Return the built-ins plus every plugin of an entry-point group.

    A plugin with a built-in's name replaces it.

    Args:
        group: The entry-point group to read plugins from.
        builtins: The registry's own entries, copied first.
        check: Validates or converts a loaded plugin; it raises to reject.
        on_error: Called with the plugin name and the error for each plugin
            that fails to load or is rejected, which is then skipped. By
            default the error is raised.

    Returns:
        Name mapped to the built-in or plugin value.

    Raises:
        LarpError: If a plugin fails and there is no ``on_error``.
    """
    registry = dict(builtins)
    for entry_point in importlib.metadata.entry_points(group=group):
        name = entry_point.name
        try:
            loaded = entry_point.load()
            registry[name] = loaded if check is None else check(name, loaded)
        except Exception as err:
            if on_error is None:
                message = f"could not load {group} plugin {name!r}: {err}"
                raise LarpError(message) from err
            on_error(name, err)
    return registry
