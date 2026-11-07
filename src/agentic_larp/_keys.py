"""Non-blocking keyboard input for POSIX and Windows terminals."""

import os
import sys
from types import TracebackType
from typing import Any, Protocol, Self

if sys.platform == "win32":  # pragma: no cover - exercised on Windows only
    import msvcrt
else:
    import select
    import termios
    import tty

_ARROWS = {"A": "up", "B": "down", "C": "right", "D": "left"}
_WINDOWS_ARROWS = {"H": "up", "P": "down", "K": "left", "M": "right"}
_ESCAPE = "\x1b"
_SEQUENCE_STARTERS = "[O"


class KeySource(Protocol):
    """Anything that can report the keys pressed since it was last asked."""

    def read(self) -> list[str]:
        """Return the keys pressed since the previous call, oldest first."""
        ...


def parse_keys(raw: str) -> list[str]:
    """Turn raw terminal input into key names.

    Printable characters map to themselves. Control input maps to ``"enter"``,
    ``"backspace"``, ``"tab"``, ``"esc"``, or an arrow (``"up"``, ``"down"``,
    ``"left"``, ``"right"``). Anything else is dropped.

    Args:
        raw: Characters exactly as the terminal delivered them.

    Returns:
        The key names, in the order they were typed.
    """
    keys: list[str] = []
    index = 0
    while index < len(raw):
        char = raw[index]
        if char == _ESCAPE and raw[index + 1 : index + 2] in tuple(_SEQUENCE_STARTERS):
            end = index + 2
            while end < len(raw) and not raw[end].isalpha() and raw[end] != "~":
                end += 1
            final = raw[end] if end < len(raw) else ""
            if final in _ARROWS:
                keys.append(_ARROWS[final])
            index = end + 1
            continue
        if char == _ESCAPE:
            keys.append("esc")
        elif char in "\r\n":
            keys.append("enter")
        elif char in "\x7f\x08":
            keys.append("backspace")
        elif char == "\t":
            keys.append("tab")
        elif char.isprintable():
            keys.append(char)
        index += 1
    return keys


def stdin_fd() -> int | None:
    """Return standard input's file descriptor, if it has a real one.

    Returns:
        The descriptor, or ``None`` when stdin is closed or replaced by an
        object without one (as under pytest).
    """
    try:
        return int(sys.stdin.fileno())
    except (OSError, ValueError, AttributeError):
        return None


def is_interactive() -> bool:
    """Return whether standard input is a terminal someone can type into."""
    fd = stdin_fd()
    return fd is not None and os.isatty(fd)


class Keys:
    """Read keys from a terminal without blocking.

    Used as a context manager: entering puts the terminal into cbreak mode
    (keys arrive immediately, unechoed) and exiting restores it. Ctrl-C still
    raises :class:`KeyboardInterrupt`. When the file descriptor is not a
    terminal, :meth:`read` always returns an empty list.
    """

    def __init__(self, fd: int | None = None) -> None:
        self.fd = stdin_fd() if fd is None else fd
        self.enabled = self.fd is not None and os.isatty(self.fd)
        self._saved: list[Any] | None = None

    def __enter__(self) -> Self:
        if self.enabled and self.fd is not None and sys.platform != "win32":
            self._saved = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._saved is not None and self.fd is not None and sys.platform != "win32":
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self._saved)
            self._saved = None

    def read(self) -> list[str]:
        """Return the keys pressed since the previous call, oldest first.

        Returns:
            Key names as produced by :func:`parse_keys`.
        """
        if not self.enabled or self.fd is None:
            return []
        if sys.platform == "win32":  # pragma: no cover - exercised on Windows only
            return _read_windows()
        raw = b""
        while select.select([self.fd], [], [], 0)[0]:
            chunk = os.read(self.fd, 1024)
            if not chunk:
                break
            raw += chunk
        return parse_keys(raw.decode(errors="ignore"))


def _read_windows() -> list[str]:  # pragma: no cover - exercised on Windows only
    keys: list[str] = []
    if sys.platform != "win32":
        return keys
    while msvcrt.kbhit():
        char = msvcrt.getwch()
        if char in {"\x00", "\xe0"}:
            arrow = _WINDOWS_ARROWS.get(msvcrt.getwch())
            if arrow:
                keys.append(arrow)
        elif char == "\x03":
            raise KeyboardInterrupt
        elif char == "\r":
            keys.append("enter")
        else:
            keys.extend(parse_keys(char))
    return keys
