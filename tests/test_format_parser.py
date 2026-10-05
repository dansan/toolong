from datetime import datetime, timezone

import pytest
from rich.text import Text

from toolong.format_parser import FormatParser

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
