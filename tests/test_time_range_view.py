import asyncio
import functools
import time

import pytest

from pilot_helpers import scanned_log_lines
from toolong.log_file import LogFile
from toolong.log_lines import LogLines
from toolong.log_view import LogView
from toolong.time_range import TimeRange
from toolong.ui import UI

DAY = TimeRange.from_strings("2026-10-02T00:00:00Z", "2026-10-02T23:59:59.999Z")

LINES = [
    "2026-10-01T23:59:59.999+00:00 INFO     [         -] Before.",
    "2026-10-02T00:00:00.000+00:00 INFO     [         -] First of the day.",
    "2026-10-02T12:00:00.000+00:00 ERROR    [         -] Boom.",
    "Traceback (most recent call last):",
    "ValueError: x",
    "2026-10-03T00:00:00.000+00:00 INFO     [         -] Next day.",
]


def write(tmp_path, name: str, lines: list[str]) -> str:
    path = tmp_path / name
    path.write_text("\n".join(lines) + "\n")
    return str(path)


def shown(log_lines: LogLines) -> list[str | None]:
    return [log_lines.get_line_from_index_blocking(index) for index in range(log_lines.line_count)]


def run_ui(app: UI, check) -> None:
    async def scenario() -> None:
        async with app.run_test(size=(160, 40)) as pilot:
            check(app, await scanned_log_lines(pilot))

    asyncio.run(scenario())


def test_single_file_shows_lines_in_range_with_their_continuation_lines(tmp_path):
    def check(app: UI, log_lines: LogLines) -> None:
        assert shown(log_lines) == LINES[1:5]
        assert app.screen.query_one(LogView).can_tail is False

    run_ui(UI([write(tmp_path, "a.log", LINES)], time_range=DAY), check)


def test_merged_files_show_lines_in_range_in_time_order(tmp_path):
    a = [
        "2026-10-02T08:00:00.000+00:00 INFO     [         -] a1",
        "2026-10-02T10:00:00.000+00:00 INFO     [         -] a2",
        "2026-10-03T08:00:00.000+00:00 INFO     [         -] a3",
    ]
    b = [
        "2026-10-01T08:00:00.000+00:00 INFO     [         -] b1",
        "2026-10-02T09:00:00.000+00:00 INFO     [         -] b2",
    ]
    paths = [write(tmp_path, "a.log", a), write(tmp_path, "b.log", b)]

    def check(app: UI, log_lines: LogLines) -> None:
        assert shown(log_lines) == [a[0], b[1], a[1]]

    run_ui(UI(paths, merge=True, time_range=DAY), check)


def test_file_without_timestamps_shows_nothing(tmp_path):
    def check(app: UI, log_lines: LogLines) -> None:
        assert log_lines.line_count == 0

    run_ui(UI([write(tmp_path, "plain.log", ["no", "timestamps"])], time_range=DAY), check)


def test_lines_of_later_scan_batches_keep_their_content(tmp_path, monkeypatch):
    # batch_time=0 makes scan_timestamps() yield a batch every 1,000 lines.
    monkeypatch.setattr(
        LogFile,
        "scan_timestamps",
        functools.partialmethod(LogFile.scan_timestamps, batch_time=0.0),
    )
    lines = [
        f"2026-10-02T00:{number // 60:02}:{number % 60:02}.000+00:00 INFO     [         -] line {number}"
        for number in range(2500)
    ]

    def check(app: UI, log_lines: LogLines) -> None:
        assert shown(log_lines) == lines

    run_ui(UI([write(tmp_path, "big.log", lines)], time_range=DAY), check)


@pytest.fixture
def central_european_time(monkeypatch):
    monkeypatch.setenv("TZ", "CET-1CEST,M3.5.0,M10.5.0/3")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


def test_naive_line_does_not_shift_later_lancelog_lines(tmp_path, central_european_time):
    lines = [
        "2026-10-02T09:00:00.000+00:00 INFO     [         -] a",
        "2026-10-02T09:00:01.000 naive local time",
        "2026-10-02T09:00:02.000+00:00 INFO     [         -] b",
        "2026-10-02T09:00:03.000+00:00 INFO     [         -] c",
    ]

    def check(app: UI, log_lines: LogLines) -> None:
        assert shown(log_lines) == lines[2:]

    time_range = TimeRange.from_strings("2026-10-02T09:00:02Z", None)
    run_ui(UI([write(tmp_path, "mixed.log", lines)], time_range=time_range), check)
