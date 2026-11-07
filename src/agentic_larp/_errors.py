"""Errors raised by agentic-larp."""


class LarpError(Exception):
    """Base class for every error this package raises on purpose."""


class GrammarError(LarpError):
    """A grammar, activity script, or pack file is malformed."""
