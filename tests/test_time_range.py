from datetime import datetime, timezone

import pytest

from toolong.time_range import TimeRange, fill_missing_timestamps


def utc(*args: int) -> float:
    return datetime(*args, tzinfo=timezone.utc).timestamp()


def make(since: str | None, until: str | None) -> TimeRange:
    time_range = TimeRange.from_strings(since, until)
    assert time_range is not None
    return time_range


def test_no_bounds_means_no_range():
    assert TimeRange.from_strings(None, None) is None


def test_offsets_and_z_are_honored():
    assert make("2026-10-02T09:00:00+02:00", None).since == utc(2026, 10, 2, 7)
    assert make("2026-10-02T07:00:00Z", None).since == utc(2026, 10, 2, 7)


def test_time_without_offset_is_local_time():
    assert make("2026-10-02T09:00", None).since == datetime(2026, 10, 2, 9).timestamp()


def test_since_and_datetime_until_are_inclusive():
    time_range = make("2026-10-02T09:00:00Z", "2026-10-02T10:00:00Z")
    assert time_range.contains(utc(2026, 10, 2, 9))
    assert time_range.contains(utc(2026, 10, 2, 10))
    assert not time_range.contains(utc(2026, 10, 2, 10, 0, 0, 1))
    assert not time_range.contains(utc(2026, 10, 2, 8, 59, 59, 999999))


def test_until_date_includes_the_whole_day():
    time_range = make("2026-10-02", "2026-10-02")
    assert time_range.contains(datetime(2026, 10, 2, 23, 59, 59, 999000).timestamp())
    assert not time_range.contains(datetime(2026, 10, 3).timestamp())


def test_open_ended_ranges():
    assert make("2026-10-02", None).contains(utc(2100, 1, 1))
    assert make(None, "2026-10-02").contains(utc(1971, 1, 1))


@pytest.mark.parametrize(("since", "until"), [("yesterday", None), (None, "02.10.2026"), ("2026-13-01", None)])
def test_invalid_times_are_rejected(since, until):
    with pytest.raises(ValueError, match="ISO 8601"):
        TimeRange.from_strings(since, until)


def test_since_after_until_is_rejected():
    with pytest.raises(ValueError, match="after"):
        TimeRange.from_strings("2026-10-03", "2026-10-02T12:00")


def test_fill_missing_timestamps_keeps_multiline_records_together():
    lines = [(0.0, 0, "a"), (5.0, 1, "a"), (0.0, 2, "a"), (0.0, 3, "a"), (9.0, 4, "a")]
    fill_missing_timestamps(lines)
    assert [seconds for seconds, _, _ in lines] == [5.0, 5.0, 5.0, 5.0, 9.0]


def test_fill_missing_timestamps_without_any_timestamp():
    lines = [(0.0, 0, "a"), (0.0, 1, "a")]
    fill_missing_timestamps(lines)
    assert [seconds for seconds, _, _ in lines] == [0.0, 0.0]
