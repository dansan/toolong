"""Restrict the shown lines to a time range (`--since` / `--until`)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TypeVar

_DATE_ONLY = re.compile(r"\d{4}-\d{2}-\d{2}")

Item = TypeVar("Item")


def _parse(text: str) -> datetime:
    text = text.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        raise ValueError(f"not an ISO 8601 date or date and time: {text!r}") from None


@dataclass(frozen=True)
class TimeRange:
    """Bounds in seconds since the epoch. `since` is inclusive; so is `until` unless `until_exclusive`."""

    since: float | None = None
    until: float | None = None
    until_exclusive: bool = False
    description: str = field(default="", compare=False)

    @classmethod
    def from_strings(cls, since: str | None, until: str | None) -> TimeRange | None:
        """Parse `--since` / `--until`; None when neither is given.

        Times without a UTC offset are local time. An `until` date without a time
        includes that whole day.
        """
        if since is None and until is None:
            return None
        since_seconds = None if since is None else _parse(since).timestamp()
        until_seconds = None
        until_exclusive = False
        if until is not None:
            moment = _parse(until)
            if _DATE_ONLY.fullmatch(until.strip()):
                moment += timedelta(days=1)
                until_exclusive = True
            until_seconds = moment.timestamp()
        time_range = cls(
            since_seconds,
            until_seconds,
            until_exclusive,
            f"from {since or 'the start'} until {until or 'the end'}",
        )
        if since_seconds is not None and not time_range.contains(since_seconds):
            raise ValueError("--since is after --until")
        return time_range

    def contains(self, seconds: float) -> bool:
        if self.since is not None and seconds < self.since:
            return False
        if self.until is None:
            return True
        return seconds < self.until if self.until_exclusive else seconds <= self.until


def fill_missing_timestamps(lines: list[tuple[float, int, Item]]) -> None:
    """Give lines without a timestamp (0.0) the timestamp of the line before.

    This keeps multi-line records such as tracebacks together. Lines before the
    first timestamp get that first timestamp.
    """
    previous = next((seconds for seconds, _, _ in lines if seconds), 0.0)
    for index, (seconds, line_no, item) in enumerate(lines):
        if seconds:
            previous = seconds
        else:
            lines[index] = (previous, line_no, item)
