"""The configurable feed grid."""

from dataclasses import dataclass

from agentic_larp._errors import LarpError

_GRID_PARTS = 2


@dataclass(frozen=True, slots=True)
class Grid:
    """A fixed number of agent feeds on screen.

    Attributes:
        columns: Feeds per row.
        rows: Rows of feeds.
    """

    columns: int
    rows: int

    @property
    def cells(self) -> int:
        """Return how many feeds fit on screen."""
        return self.columns * self.rows

    @classmethod
    def parse(cls, text: str) -> "Grid":
        """Read a ``COLSxROWS`` spec such as ``3x2``.

        Args:
            text: The spec; the ``x`` may be upper case.

        Returns:
            The grid.

        Raises:
            LarpError: If the spec is not two positive whole numbers.
        """
        parts = text.strip().lower().split("x")
        try:
            numbers = [int(part) for part in parts]
        except ValueError:
            numbers = []
        if len(numbers) != _GRID_PARTS or min(numbers, default=0) < 1:
            message = f"grid must look like COLSxROWS (for example 3x2), not {text!r}"
            raise LarpError(message)
        return cls(numbers[0], numbers[1])
