"""Payoff apps: what launches after you ship it.

An app is an :class:`App`: a name, a description and a ``run(context)``
function. Define a module-level ``APP`` in a module of this package and it is
discovered; third-party packages add apps under the ``agentic_larp.apps``
entry-point group. Most apps build a :class:`Screen` and hand it to
:func:`run_loop`.
"""

from agentic_larp.apps._base import (
    APP_ENTRY_POINT_GROUP,
    App,
    AppContext,
    Screen,
    app_registry,
    discover_apps,
    run_loop,
)

__all__ = [
    "APP_ENTRY_POINT_GROUP",
    "App",
    "AppContext",
    "Screen",
    "app_registry",
    "discover_apps",
    "run_loop",
]
