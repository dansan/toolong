from __future__ import annotations
from datetime import datetime, tzinfo
import re
from typing import Callable, NamedTuple

from toolong.lancelog import TIMESTAMP_PATTERN
from toolong.lancelog import parse_timestamp as parse_lancelog_timestamp


class TimestampFormat(NamedTuple):
    regex: str
    parser: Callable[[str], datetime | None]
    # False when an aware result doesn't come from an offset in the text (epoch seconds).
    shows_offset: bool = True


# strptime's %b expects month names in the LC_TIME locale, which ui.py sets
# from the environment, but log files use English names.
_MONTH_NUMBERS = {
    name: f"{number:02}"
    for number, name in enumerate(
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1
    )
}
_MONTH_NAME = re.compile(r"[A-Z][a-z]{2}")


def parse_timestamp(format: str, without_year: bool = False) -> Callable[[str], datetime | None]:
    """Make a parser for `format`; `without_year` puts the timestamp in the current year."""
    english_months = "%b" in format
    if english_months:
        format = format.replace("%b", "%m")
    if without_year:
        format = f"%Y {format}"

    def parse(timestamp: str) -> datetime | None:
        if english_months:
            timestamp = _MONTH_NAME.sub(
                lambda match: _MONTH_NUMBERS.get(match[0], match[0]), timestamp, count=1
            )
        if without_year:
            timestamp = f"{datetime.now().year} {timestamp}"
        try:
            return datetime.strptime(timestamp, format)
        except ValueError:
            return None

    return parse


# An offset after a naive match means the line has an aware timestamp that a
# format without an offset cut short, e.g. after its first 3 fraction digits.
_OFFSET_AFTER_MATCH = re.compile(r"\d*(?:[.,]\d+)?\s?(?:Z|[+-]\d{2}:?\d{2})")

# Info taken from logmerger project https://github.com/ptmcg/logmerger/blob/main/logmerger/timestamp_wrapper.py

TIMESTAMP_FORMATS = [
    TimestampFormat(TIMESTAMP_PATTERN, parse_lancelog_timestamp),
    TimestampFormat(
        r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}\s?(?:Z|[+-]\d{4})",
        datetime.fromisoformat,
    ),
    TimestampFormat(
        r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}",
        datetime.fromisoformat,
    ),
    TimestampFormat(
        r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}\s?(?:Z|[+-]\d{4})",
        datetime.fromisoformat,
    ),
    TimestampFormat(
        r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}",
        datetime.fromisoformat,
    ),
    TimestampFormat(
        r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\s?(?:Z|[+-]\d{4})",
        datetime.fromisoformat,
    ),
    TimestampFormat(
        r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}",
        datetime.fromisoformat,
    ),
    TimestampFormat(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2},\d{3}\s?(?:Z|[+-]\d{4})",
        datetime.fromisoformat,
    ),
    TimestampFormat(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2},\d{3}",
        datetime.fromisoformat,
    ),
    TimestampFormat(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}\s?(?:Z|[+-]\d{4}Z?)",
        datetime.fromisoformat,
    ),
    TimestampFormat(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}",
        datetime.fromisoformat,
    ),
    TimestampFormat(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\s?(?:Z|[+-]\d{4})",
        datetime.fromisoformat,
    ),
    TimestampFormat(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",
        datetime.fromisoformat,
    ),
    TimestampFormat(
        r"[JFMASOND][a-z]{2}\s(\s|\d)\d \d{2}:\d{2}:\d{2}",
        parse_timestamp("%b %d %H:%M:%S", without_year=True),
    ),
    TimestampFormat(
        r"\d{2}\/\w+\/\d{4} \d{2}:\d{2}:\d{2}",
        parse_timestamp(
            "%d/%b/%Y %H:%M:%S",
        ),
    ),
    TimestampFormat(
        r"\d{2}\/\w+\/\d{4}:\d{2}:\d{2}:\d{2} [+-]\d{4}",
        parse_timestamp("%d/%b/%Y:%H:%M:%S %z"),
    ),
    # Deprecated univention-debug format, written with 2-digit (C) or 4-digit (Python) years.
    TimestampFormat(
        r"(?<![\d.])\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}:\d{2}\.\d{3}",
        parse_timestamp("%d.%m.%Y %H:%M:%S.%f"),
    ),
    TimestampFormat(
        r"(?<![\d.])\d{2}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}\.\d{3}",
        parse_timestamp("%d.%m.%y %H:%M:%S.%f"),
    ),
    # Epoch seconds are an instant; astimezone() keeps a configured time zone from shifting them.
    TimestampFormat(
        r"\d{10}\.\d+",
        lambda s: datetime.fromtimestamp(float(s)).astimezone(),
        shows_offset=False,
    ),
    TimestampFormat(
        r"\d{13}",
        lambda s: datetime.fromtimestamp(int(s)).astimezone(),
        shows_offset=False,
    ),
]


def parse(line: str) -> tuple[TimestampFormat | None, datetime | None]:
    """Attempt to parse a timestamp."""
    for timestamp in TIMESTAMP_FORMATS:
        regex, parse_callable, _ = timestamp
        match = re.search(regex, line)
        if match is not None:
            try:
                return timestamp, parse_callable(match.string)
            except ValueError:
                continue
    return None, None


class TimestampScanner:
    """Scan a line for something that looks like a timestamp."""

    def __init__(self, timezone: tzinfo | None = None) -> None:
        """Timestamps without a UTC offset get the offset of the last timestamp with one
        (the host that wrote the file), or `timezone` before that; naive without both."""
        self._timestamp_formats = TIMESTAMP_FORMATS.copy()
        self._timezone = timezone
        self._learned_timezone: tzinfo | None = None

    def _localize(self, timestamp: datetime | None) -> datetime | None:
        if timestamp is None or timestamp.tzinfo is not None:
            return timestamp
        zone = self._learned_timezone or self._timezone
        return timestamp if zone is None else timestamp.replace(tzinfo=zone)

    def scan(self, line: str) -> datetime | None:
        """Scan a line.

        Args:
            line: A log line with a timestamp.

        Returns:
            A datetime or `None` if no timestamp was found.
        """
        if len(line) > 10_000:
            line = line[:10000]
        naive_fallback: datetime | None = None
        for index, timestamp_format in enumerate(self._timestamp_formats):
            regex, parse_callable, shows_offset = timestamp_format
            if (match := re.search(regex, line)) is not None:
                try:
                    if (timestamp := parse_callable(match.group(0))) is None:
                        continue
                except Exception:
                    continue
                if timestamp.tzinfo is None and _OFFSET_AFTER_MATCH.match(line, match.end()):
                    naive_fallback = naive_fallback or timestamp
                    continue
                if index:
                    # Put matched format at the top so that
                    # the next line will be matched quicker
                    del self._timestamp_formats[index : index + 1]
                    self._timestamp_formats.insert(0, timestamp_format)

                if timestamp.tzinfo is not None and shows_offset:
                    self._learned_timezone = timestamp.tzinfo
                return self._localize(timestamp)
        return self._localize(naive_fallback)


if __name__ == "__main__":
    # print(parse_timestamp("%Y-%m-%d %H:%M:%S%z")("2024-01-08 13:31:48+00"))
    print(parse("29/Jan/2024:13:48:00 +0000"))

    scanner = TimestampScanner()

    LINES = """\
    121.137.55.45 - - [29/Jan/2024:13:45:19 +0000] "GET /blog/rootblog/feeds/posts/ HTTP/1.1" 200 107059 "-" "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
216.244.66.233 - - [29/Jan/2024:13:45:22 +0000] "GET /robots.txt HTTP/1.1" 200 132 "-" "Mozilla/5.0 (compatible; DotBot/1.2; +https://opensiteexplorer.org/dotbot; help@moz.com)"
78.82.5.250 - - [29/Jan/2024:13:45:29 +0000] "GET /blog/tech/post/real-working-hyperlinks-in-the-terminal-with-rich/ HTTP/1.1" 200 6982 "https://www.google.com/" "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
78.82.5.250 - - [29/Jan/2024:13:45:30 +0000] "GET /favicon.ico HTTP/1.1" 200 5694 "https://www.willmcgugan.com/blog/tech/post/real-working-hyperlinks-in-the-terminal-with-rich/" "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
46.244.252.112 - - [29/Jan/2024:13:46:44 +0000] "GET /blog/tech/feeds/posts/ HTTP/1.1" 200 118238 "https://www.willmcgugan.com/blog/tech/feeds/posts/" "FreshRSS/1.23.1 (Linux; https://freshrss.org)"
92.247.181.15 - - [29/Jan/2024:13:47:33 +0000] "GET /feeds/posts/ HTTP/1.1" 200 107059 "https://www.willmcgugan.com/" "Inoreader/1.0 (+http://www.inoreader.com/feed-fetcher; 26 subscribers; )"
188.27.184.30 - - [29/Jan/2024:13:47:56 +0000] "GET /feeds/posts/ HTTP/1.1" 200 107059 "-" "Mozilla/5.0 (X11; Linux x86_64; rv:115.0) Gecko/20100101 Thunderbird/115.6.1"
198.58.103.36 - - [29/Jan/2024:13:48:00 +0000] "GET /blog/tech/feeds/tag/django/ HTTP/1.1" 200 110812 "http://www.willmcgugan.com/blog/tech/feeds/tag/django/" "Superfeedr bot/2.0 http://superfeedr.com - Make your feeds realtime: get in touch - feed-id:46271263"
3.37.46.91 - - [29/Jan/2024:13:48:19 +0000] "GET /blog/rootblog/feeds/posts/ HTTP/1.1" 200 107059 "-" "node
""".splitlines()

    for line in LINES:
        print(scanner.scan(line))
