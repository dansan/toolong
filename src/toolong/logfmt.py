"""Decode and encode logfmt the way the `logfmter` package writes it (Lancelog uses it)."""

from __future__ import annotations

import re
from typing import NamedTuple


class LogfmtPair(NamedTuple):
    key: str
    value: str
    start: int
    end: int


_PAIR = re.compile(
    r' *(?P<key>[^\s="]+)=(?:"(?P<quoted>(?:[^"\\]|\\.)*)"|(?P<bare>[^\s="]*))(?=\s|$)'
)
_ESCAPE = re.compile(r"\\(?:u([0-9a-fA-F]{4})|(.))")
_SIMPLE_ESCAPES = {"n": "\n", "t": "\t", "r": "\r"}
_NEEDS_QUOTES = re.compile(r'[ ="\x00-\x1f\x7f]')
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_CONTROL_ESCAPES = {"\n": "\\n", "\t": "\\t", "\r": "\\r"}


def unescape(value: str) -> str:
    """Decode the inside of a quoted logfmt value."""
    return _ESCAPE.sub(
        lambda match: (
            chr(int(match[1], 16))
            if match[1]
            else _SIMPLE_ESCAPES.get(match[2], match[2])
        ),
        value,
    )


def encode_value(value: str) -> str:
    """Encode a value like logfmter does, quoting it only when needed."""
    if not _NEEDS_QUOTES.search(value):
        return value
    value = value.replace("\\", "\\\\").replace('"', '\\"')
    value = _CONTROL.sub(
        lambda match: _CONTROL_ESCAPES.get(match[0], f"\\u{ord(match[0]):04x}"), value
    )
    return f'"{value}"'


def parse_pairs(data: str, offset: int = 0) -> tuple[LogfmtPair, ...] | None:
    """Split logfmt data into pairs, or return None if it isn't valid logfmt.

    `offset` is added to the positions, so they index the whole log line.
    """
    pairs: list[LogfmtPair] = []
    position = 0
    end = len(data.rstrip())
    while position < end:
        match = _PAIR.match(data, position)
        if match is None:
            return None
        quoted = match["quoted"]
        value = match["bare"] if quoted is None else unescape(quoted)
        pairs.append(
            LogfmtPair(
                match["key"], value, offset + match.start("key"), offset + match.end()
            )
        )
        position = match.end()
    return tuple(pairs)
