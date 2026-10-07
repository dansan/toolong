"""Restrict the shown lines to a time range (`--since` / `--until`)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone, tzinfo
from typing import TypeVar

_DATE_ONLY = re.compile(r"\d{4}-\d{2}-\d{2}")
_UTC_OFFSET = re.compile(r"(?:UTC)?([+-])(\d{1,2})(?::?(\d{2}))?")
DEFAULT_TIMEZONE = "Europe/Berlin"

Item = TypeVar("Item")


def parse_time(text: str) -> datetime:
    """Parse a `--since` / `--until` value, ISO 8601 with an optional `Z`."""
    iso_text = text.strip()
    if iso_text.endswith("Z"):
        iso_text = iso_text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(iso_text)
    except ValueError:
        raise ValueError(f"not an ISO 8601 date or date and time: {text!r}") from None


def parse_timezone(text: str) -> tzinfo:
    """Parse an IANA time zone name (`Europe/Berlin`), `UTC`, or an offset (`+02:00`, `UTC+2`)."""
    name = text.strip()
    if name.upper() in ("UTC", "Z"):
        return timezone.utc
    if match := _UTC_OFFSET.fullmatch(name):
        sign, hours, minutes = match.groups()
        offset = timedelta(hours=int(hours), minutes=int(minutes or 0))
        if offset >= timedelta(hours=24):
            raise ValueError(f"not a time zone: {text!r}")
        return timezone(-offset if sign == "-" else offset)
    try:
        from zoneinfo import ZoneInfo
    except ImportError:  # Python 3.8
        raise ValueError(f"time zone names need Python 3.9 or later: {text!r}") from None
    try:
        return ZoneInfo(name)
    except (KeyError, ValueError):
        raise ValueError(f"not a time zone: {text!r}") from None


@dataclass(frozen=True)
class TimeRange:
    """Bounds in seconds since the epoch. `since` is inclusive; so is `until` unless `until_exclusive`."""

    since: float | None = None
    until: float | None = None
    until_exclusive: bool = False
    description: str = field(default="", compare=False)

    @classmethod
    def from_strings(
        cls, since: str | None, until: str | None, zone: tzinfo | None = None
    ) -> TimeRange | None:
        """Parse `--since` / `--until`; None when neither is given.

        Times without a UTC offset are in `zone`, or local time without one. An
        `until` date without a time includes that whole day.
        """
        if since is None and until is None:
            return None

        def parse(text: str) -> datetime:
            moment = parse_time(text)
            if moment.tzinfo is None and zone is not None:
                moment = moment.replace(tzinfo=zone)
            return moment

        since_seconds = None if since is None else parse(since).timestamp()
        until_seconds = None
        until_exclusive = False
        if until is not None:
            moment = parse(until)
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
