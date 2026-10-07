import asyncio
import functools
import time

import pytest

from pilot_helpers import scanned_log_lines
from toolong.log_file import LogFile
from toolong.log_lines import LogLines
from toolong.log_view import LogView
from toolong.time_range import TimeRange, parse_timezone
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


def notifications(app: UI) -> list[str]:
    return [notification.message for notification in app._notifications]


def test_single_file_messages_name_the_file_and_do_not_say_merged(tmp_path):
    def check(app: UI, log_lines: LogLines) -> None:
        assert notifications(app) == [
            "4 lines in a.log from 2026-10-02T00:00:00Z until 2026-10-02T23:59:59.999Z",
        ]
        app.screen.query_one(LogView).action_toggle_tail()

    async def scenario() -> None:
        app = UI([write(tmp_path, "a.log", LINES)], time_range=DAY)
        async with app.run_test(size=(160, 40)) as pilot:
            check(app, await scanned_log_lines(pilot))
            await pilot.pause()
            assert notifications(app)[-1] == "Can't tail a time-filtered view"

    asyncio.run(scenario())


def test_each_tab_names_its_file(tmp_path):
    paths = [write(tmp_path, "a.log", LINES), write(tmp_path, "b.log", LINES[:2])]

    def check(app: UI, log_lines: LogLines) -> None:
        assert "4 lines in a.log from 2026-10-02T00:00:00Z until 2026-10-02T23:59:59.999Z" in notifications(app)

    run_ui(UI(paths, time_range=DAY), check)


def test_empty_file_gets_no_missing_timestamps_warning(tmp_path):
    path = tmp_path / "empty.log"
    path.write_text("")

    def check(app: UI, log_lines: LogLines) -> None:
        assert not any("No timestamps" in message for message in notifications(app))

    run_ui(UI([str(path)], time_range=DAY), check)


def test_file_without_timestamps_gets_a_warning(tmp_path):
    def check(app: UI, log_lines: LogLines) -> None:
        assert "No timestamps found in 'plain.log'" in notifications(app)

    run_ui(UI([write(tmp_path, "plain.log", ["no", "timestamps"])], time_range=DAY), check)


def test_records_with_equal_timestamps_stay_contiguous_when_merged(tmp_path):
    a = [
        "2026-10-02T09:00:00.000+00:00 ERROR    [         -] a boom",
        "Traceback (most recent call last):",
        "ValueError: a",
    ]
    b = [
        "2026-10-02T08:00:00.000+00:00 INFO     [         -] b1",
        "2026-10-02T09:00:00.000+00:00 INFO     [         -] b2",
        "b2 continued",
    ]
    paths = [write(tmp_path, "a.log", a), write(tmp_path, "b.log", b)]

    def check(app: UI, log_lines: LogLines) -> None:
        assert shown(log_lines) == [b[0], *a, b[1], b[2]]

    run_ui(UI(paths, merge=True, time_range=DAY), check)


def test_output_path_gets_the_lines_in_range(tmp_path):
    out = tmp_path / "out.log"

    async def scenario() -> None:
        app = UI([write(tmp_path, "a.log", LINES)], save_merge=str(out), time_range=DAY)
        async with app.run_test(size=(160, 40)) as pilot:
            await scanned_log_lines(pilot)
            for _ in range(100):
                if f"Saved lines to {str(out)!r}" in notifications(app):
                    break
                await pilot.pause(0.05)
            assert notifications(app)[-1] == f"Saved lines to {str(out)!r}"

    asyncio.run(scenario())
    assert out.read_text().splitlines() == LINES[1:5]


def test_lines_before_the_first_timestamp_in_a_later_batch_get_that_timestamp(tmp_path, monkeypatch):
    monkeypatch.setattr(
        LogFile,
        "scan_timestamps",
        functools.partialmethod(LogFile.scan_timestamps, batch_time=0.0),
    )
    lines = [f"no timestamp {number}" for number in range(1200)] + LINES

    def check(app: UI, log_lines: LogLines) -> None:
        assert shown(log_lines) == LINES[1:5]

    early_range = TimeRange.from_strings("2026-10-01", "2026-10-02T23:59:59Z")
    lines_with_early_start = [f"no timestamp {number}" for number in range(1200)] + LINES[1:]

    def check_kept(app: UI, log_lines: LogLines) -> None:
        assert shown(log_lines) == lines_with_early_start[:-1]

    run_ui(UI([write(tmp_path, "late.log", lines)], time_range=DAY), check)
    run_ui(UI([write(tmp_path, "kept.log", lines_with_early_start)], time_range=early_range), check_kept)


def test_deprecated_timestamps_use_the_offset_of_the_other_records(tmp_path):
    lines = [
        "2026-10-04T05:05:23.470110+00:00     INIT ",
        "04.10.26 05:05:23.976  DEBUG_INIT",
        "2026-10-04T05:05:48.000000+00:00     INFO [         -] Started.\t| pid=1 func=main.run:1",
    ]
    path = write(tmp_path, "udm.log", lines)
    time_range = TimeRange.from_strings("2026-10-04T05:05:23.900Z", "2026-10-04T05:05:24Z")

    def check(app: UI, log_lines: LogLines) -> None:
        assert shown(log_lines) == [lines[1]]

    run_ui(UI([path], time_range=time_range, timezone=parse_timezone("Europe/Berlin")), check)


def test_timezone_places_files_with_only_deprecated_timestamps(tmp_path):
    lines = ["06.10.26 23:20:33.803  DEBUG_INIT", "06.10.26 23:20:34.000  LISTENER    ( PROCESS ) : x"]
    path = write(tmp_path, "old.log", lines)
    # 21:20:33Z to 21:20:33.900Z contains the first line only if it is Berlin time.
    time_range = TimeRange.from_strings("2026-10-06T21:20:33Z", "2026-10-06T21:20:33.900Z")

    def check_berlin(app: UI, log_lines: LogLines) -> None:
        assert shown(log_lines) == [lines[0]]

    def check_utc(app: UI, log_lines: LogLines) -> None:
        assert shown(log_lines) == []

    run_ui(UI([path], time_range=time_range, timezone=parse_timezone("Europe/Berlin")), check_berlin)
    run_ui(UI([path], time_range=time_range, timezone=parse_timezone("UTC")), check_utc)
