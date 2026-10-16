"""Decode LDAP distinguished names in the string form of RFC 4514, for display."""

from __future__ import annotations

import re
from typing import NamedTuple

# Longer values aren't parsed, so a huge value can't slow down the line details.
MAX_DN_LENGTH = 4096

# Every attribute starts with its type and "=", so most other values fail at their first characters.
_TYPE_AND_EQUALS = re.compile(r"(?:[A-Za-z][A-Za-z0-9-]*|[0-9]+(?:\.[0-9]+)*)=")
_HEX_STRING = re.compile(r"#(?:[0-9A-Fa-f]{2})+")
_HEX_DIGITS = "0123456789abcdefABCDEF"
_ESCAPABLE = '"+,;<> #=\\'
# RFC 4514 allows raw control characters, but rejecting them stops at the first line of multi-line values.
_NOT_IN_STRING = '"+,;<>\\' + "".join(map(chr, range(0x20))) + "\x7f"


class Ava(NamedTuple):
    """An attribute type and its decoded value; a "#" hex string value is kept undecoded."""

    type: str
    value: str


def parse_dn(text: str) -> list[list[Ava]] | None:
    """Split a DN into RDNs and decode its values, or return None if `text` isn't a DN."""
    if len(text) > MAX_DN_LENGTH or not _TYPE_AND_EQUALS.match(text):
        return None
    rdns: list[list[Ava]] = [[]]
    position = 0
    while True:
        attribute_type = _TYPE_AND_EQUALS.match(text, position)
        if attribute_type is None:
            return None
        position = attribute_type.end()
        hex_string = _HEX_STRING.match(text, position)
        if hex_string is not None:
            value: str | None = hex_string[0]
            position = hex_string.end()
        else:
            value, position = _decode_value(text, position)
            if value is None:
                return None
        rdns[-1].append(Ava(attribute_type[0][:-1], value))
        if position == len(text):
            return rdns
        if text[position] == ",":
            rdns.append([])
        elif text[position] != "+":
            return None
        position += 1


def _decode_value(text: str, position: int) -> tuple[str | None, int]:
    """Decode a string value up to the next unescaped "," or "+"."""
    start = position
    octets = bytearray()
    escaped_until = start
    while position < len(text) and text[position] not in ",+":
        char = text[position]
        if char == "\\":
            pair = text[position + 1 : position + 3]
            if len(pair) == 2 and pair[0] in _HEX_DIGITS and pair[1] in _HEX_DIGITS:
                octets.append(int(pair, 16))
                position += 3
            elif pair and pair[0] in _ESCAPABLE:
                octets += pair[0].encode()
                position += 2
            else:
                return None, position
            escaped_until = position
        elif char in _NOT_IN_STRING:
            return None, position
        else:
            # A lone surrogate from a logfmt "\u" escape must not raise here; decoding rejects it.
            octets += char.encode("utf-8", "surrogatepass")
            position += 1
    raw = text[start:position]
    if raw.startswith((" ", "#")) or (raw.endswith(" ") and escaped_until < position):
        return None, position
    try:
        return octets.decode("utf-8"), position
    except UnicodeDecodeError:
        return None, position
