"""Payoff apps: what launches after you ship it.

An app is any callable ``run(context: AppContext) -> None``. Most apps build a
:class:`Screen` and hand it to :func:`run_loop`. Third-party packages add apps
under the ``agentic_larp.apps`` entry-point group.
"""

from agentic_larp.apps._base import (
    DESCRIPTIONS,
    ENTRY_POINT_GROUP,
    App,
    AppContext,
    Screen,
    app_registry,
    run_loop,
)

__all__ = [
    "DESCRIPTIONS",
    "ENTRY_POINT_GROUP",
    "App",
    "AppContext",
    "Screen",
    "app_registry",
    "run_loop",
]
