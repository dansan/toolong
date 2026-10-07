import calendar
import locale
from datetime import datetime, timedelta, timezone

import pytest

from toolong.timestamps import TimestampScanner


def test_scanner_keeps_utc_offset_with_colon():
    timestamp = TimestampScanner().scan("2026-10-02T09:38:28.970+00:00 INFO     [-] x")
    assert timestamp == datetime(2026, 10, 2, 9, 38, 28, 970000, tzinfo=timezone.utc)


def test_scanner_keeps_microseconds_and_negative_offsets():
    timestamp = TimestampScanner().scan("2023-10-27T08:22:57.275138-05:00 INFO     [-] x")
    assert timestamp is not None
    assert timestamp.utcoffset() == timedelta(hours=-5)
    assert timestamp.microsecond == 275138


@pytest.mark.parametrize("offset", ["+0000", "Z", "+00:00"])
def test_scanner_returns_aware_microseconds_for_lancelog_offsets(offset):
    timestamp = TimestampScanner().scan(f"2026-10-02T09:38:28.970123{offset} INFO     [-] x")
    assert timestamp == datetime(2026, 10, 2, 9, 38, 28, 970123, tzinfo=timezone.utc)


def test_naive_iso_line_does_not_make_later_offset_lines_naive():
    scanner = TimestampScanner()
    lines = [
        "2026-10-02T09:00:00.000+00:00 INFO     [-] a",
        "2026-10-02T09:00:01.000 x",
        "2026-10-02T09:00:02.000+00:00 INFO     [-] b",
        "2026-10-02T09:00:03.123456+00:00 INFO     [-] c",
    ]
    timestamps = [scanner.scan(line) for line in lines]
    assert None not in timestamps
    assert [ts is not None and ts.tzinfo is not None for ts in timestamps] == [True, False, True, True]


def test_offset_the_aware_formats_miss_still_gives_the_naive_time():
    timestamp = TimestampScanner().scan("2026-10-02 09:00:01+00:00 x")
    assert timestamp == datetime(2026, 10, 2, 9, 0, 1)


def test_syslog_timestamp_gets_the_current_year():
    timestamp = TimestampScanner().scan("Oct  2 09:00:01 host sshd[1]: x")
    assert timestamp == datetime(datetime.now().year, 10, 2, 9, 0, 1)


def test_syslog_february_29_needs_a_leap_year():
    year = datetime.now().year
    timestamp = TimestampScanner().scan("Feb 29 09:00:01 host sshd[1]: x")
    assert timestamp == (datetime(year, 2, 29, 9, 0, 1) if calendar.isleap(year) else None)


@pytest.fixture
def german_time_locale():
    previous = locale.setlocale(locale.LC_TIME)
    try:
        locale.setlocale(locale.LC_TIME, "de_DE.UTF-8")
    except locale.Error:
        pytest.skip("de_DE.UTF-8 locale not installed")
    yield
    locale.setlocale(locale.LC_TIME, previous)


@pytest.mark.parametrize(
    "line, expected",
    [
        ("Oct  2 09:00:01 host sshd[1]: x", datetime(datetime.now().year, 10, 2, 9, 0, 1)),
        ('1.2.3.4 - - [29/Oct/2024 13:45:19] "GET /"', datetime(2024, 10, 29, 13, 45, 19)),
        (
            '1.2.3.4 - - [29/Oct/2024:13:45:19 +0000] "GET /"',
            datetime(2024, 10, 29, 13, 45, 19, tzinfo=timezone.utc),
        ),
    ],
)
def test_english_month_names_parse_in_any_locale(german_time_locale, line, expected):
    assert TimestampScanner().scan(line) == expected


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("06.10.26 23:20:33.803  DEBUG_INIT", datetime(2026, 10, 6, 23, 20, 33, 803000)),
        ("13.08.2008 13:13:57.123 LISTENER    (ERROR  ): x", datetime(2008, 8, 13, 13, 13, 57, 123000)),
    ],
)
def test_scanner_reads_deprecated_univention_debug_timestamps(line, expected):
    assert TimestampScanner().scan(line) == expected


def test_scanner_puts_timestamps_without_offset_in_the_given_timezone():
    berlin = timezone(timedelta(hours=2))
    scanner = TimestampScanner(timezone=berlin)
    assert scanner.scan("06.10.26 23:20:33.803  DEBUG_INIT") == datetime(
        2026, 10, 6, 23, 20, 33, 803000, tzinfo=berlin
    )


def test_scanner_keeps_the_offset_of_aware_timestamps_with_a_timezone():
    scanner = TimestampScanner(timezone=timezone(timedelta(hours=2)))
    timestamp = scanner.scan("2026-10-02T09:38:28.970+00:00 INFO     [-] x")
    assert timestamp is not None
    assert timestamp.utcoffset() == timedelta(0)
