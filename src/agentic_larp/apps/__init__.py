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
    Outcome,
    Screen,
    app_registry,
    run_loop,
)
from agentic_larp.apps._meltdown import (
    SHARED_ERRORS,
    capture_frame,
    decay,
    run_meltdown,
)

__all__ = [
    "DESCRIPTIONS",
    "ENTRY_POINT_GROUP",
    "SHARED_ERRORS",
    "App",
    "AppContext",
    "Outcome",
    "Screen",
    "app_registry",
    "capture_frame",
    "decay",
    "run_loop",
    "run_meltdown",
]
