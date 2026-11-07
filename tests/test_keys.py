import os
from typing import Any

import pytest

from agentic_larp import Keys, is_interactive, parse_keys


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("abc", ["a", "b", "c"]),
        ("\r", ["enter"]),
        ("\n", ["enter"]),
        ("\x7f\x08", ["backspace", "backspace"]),
        ("\t", ["tab"]),
        ("\x1b", ["esc"]),
        ("\x1b[A\x1b[B\x1b[C\x1b[D", ["up", "down", "right", "left"]),
        ("\x1bOA", ["up"]),
        ("\x1b[3~x", ["x"]),
        ("\x1b[1;5", []),
        ("\x01\x02", []),
        ("ship it\r", [*"ship it", "enter"]),
    ],
)
def test_parse_keys_names_terminal_input(raw: str, expected: list[str]) -> None:
    assert parse_keys(raw) == expected


def settled_attributes(fd: int) -> list[Any]:
    """Terminal attributes minus PENDIN, which the kernel sets and clears by itself."""
    import termios  # noqa: PLC0415 - POSIX-only module, imported where used

    attributes = termios.tcgetattr(fd)
    attributes[3] &= ~termios.PENDIN
    return attributes


def test_keys_reads_from_a_terminal_and_restores_it() -> None:
    controller, terminal = os.openpty()
    try:
        before = settled_attributes(terminal)
        with Keys(fd=terminal) as keys:
            assert keys.enabled
            assert keys.read() == []
            os.write(controller, b"hi\x1b[A\r")
            assert keys.read() == ["h", "i", "up", "enter"]
        assert settled_attributes(terminal) == before
    finally:
        os.close(controller)
        os.close(terminal)


def test_keys_is_silent_when_not_a_terminal() -> None:
    reader, writer = os.pipe()
    try:
        os.write(writer, b"abc")
        with Keys(fd=reader) as keys:
            assert not keys.enabled
            assert keys.read() == []
    finally:
        os.close(reader)
        os.close(writer)


def test_keys_without_a_real_stdin_is_disabled() -> None:
    # pytest replaces stdin with an object that has no file descriptor.
    assert not is_interactive()
    with Keys() as keys:
        assert keys.read() == []
