from datetime import datetime, timezone
import time

import pytest
from rich.text import Text

from toolong.format_parser import CombinedLogFormat, FormatParser

LINE = (
    "2026-10-02T09:38:28.970+00:00 WARNING  [         -] Disk almost full.\t| free_mb=12 _source=disk.check:7"
).expandtabs(4)


def styles_at(text: Text, index: int) -> list[str]:
    return [str(span.style) for span in text.spans if span.start <= index < span.end]


def test_lancelog_line_has_an_aware_timestamp_and_unchanged_text():
    timestamp, line, text = FormatParser().parse(LINE)
    assert timestamp == datetime(2026, 10, 2, 9, 38, 28, 970000, tzinfo=timezone.utc)
    assert line == LINE
    assert text.plain == LINE


def test_record_uses_level_color_and_data_is_gray():
    _, _, text = FormatParser().parse(LINE)
    assert styles_at(text, LINE.index("2026")) == ["yellow"]
    assert styles_at(text, LINE.index("Disk")) == ["yellow"]
    assert styles_at(text, LINE.index("|")) == ["grey50"]
    assert styles_at(text, LINE.index("free_mb")) == ["grey50"]


@pytest.mark.parametrize(
    ("level", "styles"),
    [
        ("TRACE", ["grey50"]),
        ("DEBUG", ["grey50"]),
        ("INFO", []),
        ("WARNING", ["yellow"]),
        ("ERROR", ["red"]),
        ("CRITICAL", ["red"]),
    ],
)
def test_level_colors(level, styles):
    line = f"2026-10-02T09:38:28.970+00:00 {level:<8} [         -] Message.\t| k=v".expandtabs(4)
    _, _, text = FormatParser().parse(line)
    assert styles_at(text, line.index("Message")) == styles


def test_line_without_data_section_is_all_level_colored():
    line = "2026-10-02T09:38:28.970+00:00 ERROR    [         -] Boom."
    _, _, text = FormatParser().parse(line)
    assert styles_at(text, line.index("Boom")) == ["red"]


def test_other_lines_still_use_the_default_format():
    timestamp, line, text = FormatParser().parse('  record["message"] = x')
    assert timestamp is None
    assert text.plain == line


@pytest.mark.parametrize(
    ("level", "styles"),
    [("ALL", ["grey50"]), ("PROCESS", []), ("WARN", ["yellow"])],
)
def test_univention_debug_level_names_in_lancelog_header(level, styles):
    line = f"2026-10-02T09:38:28.970+00:00 {level:>8} [         -] Message.\t| k=v".expandtabs(4)
    _, _, text = FormatParser().parse(line)
    assert styles_at(text, line.index("Message")) == styles


@pytest.mark.parametrize(
    ("line", "styles"),
    [
        ("06.10.26 23:20:33.803  LISTENER    ( PROCESS ) : Message", []),
        ("06.10.26 23:20:33.803  LISTENER    ( ALL     ) : Message", ["grey50"]),
        ("06.10.26 23:20:33.803  LISTENER    ( INFO    ) : Message", []),
        ("06.10.26 23:20:33.803  LISTENER    ( WARN    ) : Message", ["yellow"]),
        ("06.10.26 23:20:33.803  LISTENER    ( ERROR   ) : Message", ["red"]),
        ("13.08.2008 13:13:57.123 LISTENER    (ERROR  ): Message", ["red"]),
        ("06.10.26 23:20:33.803  LISTENER    ( 7       ) : Message", []),
    ],
)
def test_univention_debug_lines_use_their_level_color(line, styles):
    _, parsed_line, text = FormatParser().parse(line)
    assert parsed_line == line
    assert text.plain == line
    assert styles_at(text, line.index("Message")) == styles


@pytest.mark.parametrize("marker", ["DEBUG_INIT", "DEBUG_EXIT"])
def test_univention_debug_init_and_exit_lines_are_gray(marker):
    line = f"06.10.26 23:20:33.803  {marker}"
    timestamp, _, text = FormatParser().parse(line)
    assert timestamp == datetime(2026, 10, 6, 23, 20, 33, 803000)
    assert styles_at(text, line.index(marker)) == ["grey50"]


def test_univention_debug_lines_with_numeric_levels_are_recognized():
    timestamp, _, _ = FormatParser().parse("06.10.26 23:20:33.803  LISTENER    ( 7       ) : Message")
    assert timestamp == datetime(2026, 10, 6, 23, 20, 33, 803000)


def test_very_long_line_parses_quickly():
    start = time.perf_counter()
    timestamp, _, _ = FormatParser().parse("x " * 200_000)
    assert time.perf_counter() - start < 5
    assert timestamp is None


def test_common_log_line_is_still_recognized():
    timestamp, _, _ = FormatParser().parse(
        '127.0.0.1 - - [02/Oct/2026:09:38:28 +0000] "GET /index.html HTTP/1.1" 200 512 "-"'
    )
    assert timestamp == datetime(2026, 10, 2, 9, 38, 28, tzinfo=timezone.utc)


def test_long_combined_log_line_is_recognized_and_shown_in_full():
    line = (
        '127.0.0.1 - - [02/Oct/2026:09:38:28 +0000] "GET /index.html HTTP/1.1" 200 512 "-" "curl/8.0" - 42 '
        + "host" * 1000
    )
    _, _, text = CombinedLogFormat().parse(line)
    assert text.plain == line
