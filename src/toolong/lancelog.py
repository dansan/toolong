"""Parse log lines in the Lancelog format (Univention ADR 0010 "Log Format").

<timestamp> <level> [<request ID>] <message>\t| <logfmt data>
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from functools import cached_property

from toolong.logfmt import LogfmtPair, parse_pairs

HEADER_KEYS = ("level", "request_id", "message")
TAB_SIZE = 4

_LINE = re.compile(
    r"(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3,6}(?:Z|[+-]\d{2}:?\d{2})) +"
    r"(?P<level>\w+) +\[(?P<request_id>[^\]]*)\] (?P<rest>.*)"
)
# LogFile.get_line() expands tabs, so "\t| " may arrive as spaces that end on a tab stop.
_SEPARATOR = re.compile(r"(?:\t| {1,4})\| ")


@dataclass(frozen=True)
class LancelogRecord:
    timestamp: datetime | None
    level: str
    request_id: str
    message: str
    pairs: tuple[LogfmtPair, ...]
    # Positions in the line of "level", "request_id", "message" and, if present, "separator".
    spans: dict[str, tuple[int, int]]
    # False when the text after the separator isn't valid logfmt.
    data_valid: bool

    @cached_property
    def fields(self) -> dict[str, str]:
        fields = {
            "level": self.level,
            "request_id": self.request_id,
            "message": self.message,
        }
        fields.update((pair.key, pair.value) for pair in self.pairs)
        return fields

    def field_span(self, key: str) -> tuple[int, int] | None:
        for pair in reversed(self.pairs):
            if pair.key == key:
                return pair.start, pair.end
        return self.spans.get(key) if key in HEADER_KEYS else None


def _find_data(
    line: str, start: int
) -> tuple[tuple[int, int] | None, tuple[LogfmtPair, ...] | None]:
    """Return the separator span and the parsed data after it.

    A "|" in the message can look like a separator, so the first one followed by
    valid logfmt wins. Without any, the first separator is used and the data is None.
    """
    first: tuple[int, int] | None = None
    for separator in _SEPARATOR.finditer(line, start):
        pipe = separator.end() - 2
        if line[separator.start()] == " " and pipe % TAB_SIZE:
            continue
        pairs = parse_pairs(line[separator.end() :], separator.end())
        if pairs is not None:
            return separator.span(), pairs
        first = first or separator.span()
    return first, None


def parse_lancelog(line: str) -> LancelogRecord | None:
    """Parse a raw or tab-expanded Lancelog line, or return None for other lines."""
    line = line.rstrip("\r\n")
    match = _LINE.match(line)
    if match is None:
        return None
    try:
        timestamp = datetime.fromisoformat(match["timestamp"].replace("Z", "+00:00"))
    except ValueError:
        timestamp = None
    rest_start = match.start("rest")
    separator, pairs = _find_data(line, rest_start)
    message_end = len(line) if separator is None else separator[0]
    message = line[rest_start:message_end].rstrip(" ")
    raw_request_id = match["request_id"]
    request_id = raw_request_id.strip()
    request_id_start = match.start("request_id") + (
        len(raw_request_id) - len(raw_request_id.lstrip())
    )
    spans = {
        "level": match.span("level"),
        "request_id": (request_id_start, request_id_start + len(request_id)),
        "message": (rest_start, rest_start + len(message)),
    }
    if separator is not None:
        spans["separator"] = separator
    return LancelogRecord(
        timestamp=timestamp,
        level=match["level"],
        request_id=request_id,
        message=message,
        pairs=pairs or (),
        spans=spans,
        data_valid=separator is None or pairs is not None,
    )
