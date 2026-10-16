"""Turn an ADR 0010 line into a one-line Python dict literal or JSON object."""

from __future__ import annotations

import json
import math
import re
from typing import NamedTuple

from toolong.adr_0010 import parse_adr_0010

Value = str | int | float | bool

# Without leading zeros: "007" or "0755" is an ID or a file mode, not a number.
_INT = re.compile(r"-?(?:0|[1-9][0-9]*)")
_FLOAT = re.compile(r"-?(?:(?:0|[1-9][0-9]*)\.[0-9]*|\.[0-9]+)")
_LINE_SEPARATOR_ESCAPES = {0x85: "\\u0085", 0x2028: "\\u2028", 0x2029: "\\u2029"}


class Export(NamedTuple):
    # None when there is nothing to copy; `problems` then says why.
    text: str | None
    problems: list[str]


def export_line(raw: bytes, as_json: bool) -> Export:
    """Export the header and the logfmt-decoded data of a raw ADR 0010 line."""
    problems: list[str] = []
    try:
        line = raw.decode("utf-8")
    except UnicodeDecodeError:
        line = raw.decode("utf-8", errors="replace")
        problems.append("The line isn't valid UTF-8; invalid bytes were copied as �.")
    record = parse_adr_0010(line)
    if record is None:
        return Export(None, ["This line isn't an ADR 0010 record. Nothing was copied."])
    if not record.data_valid:
        return Export(None, ["The data after | isn't valid logfmt. Nothing was copied."])
    data: dict[str, Value] = {
        "_timestamp": record.timestamp_text,
        "_level": record.level,
        "_request_id": record.request_id,
        "_message": record.message,
    }
    seen: set[str] = set()
    for pair in record.pairs:
        if pair.key in seen:
            problems.append(f"Data key {pair.key!r} appears more than once; the last value was copied.")
        elif pair.key in data:
            problems.append(f"Data key {pair.key!r} replaced the header value of the same name.")
        seen.add(pair.key)
        data[pair.key] = typed_value(pair.value)
    return Export(to_json(data) if as_json else repr(data), problems)


def typed_value(value: str) -> Value:
    """Convert `true`, `false` and decimal numbers; keep all other values as strings."""
    if value in ("true", "false"):
        return value == "true"
    try:
        if _INT.fullmatch(value):
            return int(value)
        if _FLOAT.fullmatch(value):
            number = float(value)
            # Infinity is neither JSON nor a Python literal.
            return number if math.isfinite(number) else value
    except ValueError:
        # int() refuses more than sys.get_int_max_str_digits() digits.
        pass
    return value


def to_json(data: dict[str, Value]) -> str:
    text = json.dumps(data, ensure_ascii=False)
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        # Lone surrogates from logfmt "\u" escapes have no UTF-8 encoding; ASCII escapes them.
        return json.dumps(data)
    # Valid in JSON strings, but splitlines() and some editors break lines there.
    return text.translate(_LINE_SEPARATOR_ESCAPES)
