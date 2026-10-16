"""Turn a Lancelog line into a one-line Python dict literal or JSON object."""

from __future__ import annotations

import json
from typing import NamedTuple

from toolong.lancelog import parse_lancelog


class Export(NamedTuple):
    # None when there is nothing to copy; `problems` then says why.
    text: str | None
    problems: list[str]


def export_line(raw: bytes, as_json: bool) -> Export:
    """Export the header and the logfmt-decoded data of a raw Lancelog line."""
    problems: list[str] = []
    try:
        line = raw.decode("utf-8")
    except UnicodeDecodeError:
        line = raw.decode("utf-8", errors="replace")
        problems.append("The line isn't valid UTF-8; invalid bytes were copied as �.")
    record = parse_lancelog(line)
    if record is None:
        return Export(None, ["This line isn't a Lancelog record. Nothing was copied."])
    if not record.data_valid:
        return Export(None, ["The data after | isn't valid logfmt. Nothing was copied."])
    data = {
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
        data[pair.key] = pair.value
    return Export(to_json(data) if as_json else repr(data), problems)


def to_json(data: dict[str, str]) -> str:
    text = json.dumps(data, ensure_ascii=False)
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        # Lone surrogates from logfmt "\u" escapes have no UTF-8 encoding; ASCII escapes them.
        return json.dumps(data)
    return text
