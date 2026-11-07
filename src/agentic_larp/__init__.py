"""Cosplay as a 10x AI engineer: a terminal UI where a swarm of fake agents builds your app, then ships it.

The root is tiny on purpose. The rest of the public API lives in submodules:
``cli``, ``sim``, ``events``, ``stages``, ``widgets``, ``packs``, ``policies``,
``keys``, ``apps``, ``meltdown`` and ``plugins``.
"""

from importlib.metadata import version

from agentic_larp._cli import main
from agentic_larp._errors import GrammarError, LarpError

__all__ = ["GrammarError", "LarpError", "__version__", "main"]

__version__ = version("agentic-larp")
