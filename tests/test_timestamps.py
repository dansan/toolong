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
