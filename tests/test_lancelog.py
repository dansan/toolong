from datetime import datetime, timedelta, timezone

import pytest

from toolong.lancelog import parse_lancelog

HEADER = "2026-10-02T09:38:28.970+00:00 INFO     [         -] "
LINE = HEADER + "Effective log level.\t| event=log_level_effective effective_level=TRACE _source=sync.main:444"


def test_header_fields():
    record = parse_lancelog(LINE)
    assert record is not None
    assert record.timestamp == datetime(2026, 10, 2, 9, 38, 28, 970000, tzinfo=timezone.utc)
    assert (record.level, record.request_id, record.message) == ("INFO", "-", "Effective log level.")


def test_data_fields_follow_header_fields():
    record = parse_lancelog(LINE)
    assert record is not None
    assert record.fields == {
        "level": "INFO",
        "request_id": "-",
        "message": "Effective log level.",
        "event": "log_level_effective",
        "effective_level": "TRACE",
        "_source": "sync.main:444",
    }


def test_tab_expanded_line_parses_like_the_raw_line():
    raw = parse_lancelog(LINE)
    expanded = parse_lancelog(LINE.expandtabs(4))
    assert raw is not None and expanded is not None
    assert expanded.fields == raw.fields
    assert expanded.data_valid


def test_spans_point_into_the_line():
    line = LINE.expandtabs(4)
    record = parse_lancelog(line)
    assert record is not None
    assert line[slice(*record.spans["level"])] == "INFO"
    assert line[slice(*record.spans["request_id"])] == "-"
    assert line[slice(*record.spans["message"])] == "Effective log level."
    assert line[slice(*record.spans["separator"])].endswith("| ")
    event_span = record.field_span("event")
    assert event_span is not None
    assert line[slice(*event_span)] == "event=log_level_effective"


def test_line_without_data_section():
    record = parse_lancelog("2023-10-27T08:22:57.275138+00:00 INFO     [31f863092a] modified group")
    assert record is not None
    assert record.message == "modified group"
    assert record.pairs == ()
    assert record.data_valid
    assert "separator" not in record.spans


def test_escaped_separator_stays_in_message():
    line = HEADER + "a\t\\| b\t| k=v"
    record = parse_lancelog(line)
    assert record is not None
    assert record.message == "a\t\\| b"
    assert record.fields["k"] == "v"
    expanded = parse_lancelog(line.expandtabs(4))
    assert expanded is not None
    assert expanded.fields["k"] == "v"


def test_pipe_in_message_off_a_tab_stop_is_not_a_separator():
    record = parse_lancelog((HEADER + "x | y\t| k=v").expandtabs(4))
    assert record is not None
    assert record.message == "x | y"
    assert record.fields["k"] == "v"


def test_pipe_in_message_on_a_tab_stop_is_skipped_without_logfmt_after_it():
    record = parse_lancelog((HEADER + "xyz | w\t| k=v").expandtabs(4))
    assert record is not None
    assert record.message == "xyz | w"
    assert record.fields["k"] == "v"


def test_malformed_data_keeps_header_fields():
    record = parse_lancelog(HEADER + 'msg\t| a="unterminated')
    assert record is not None
    assert not record.data_valid
    assert record.message == "msg"
    assert record.pairs == ()
    assert record.fields["level"] == "INFO"


def test_data_request_id_replaces_shortened_header_value():
    line = "2023-10-27T08:22:57.275138+00:00 INFO     [31f863092a] modified group\t| request_id=31f863092ade1cb"
    record = parse_lancelog(line)
    assert record is not None
    assert record.request_id == "31f863092a"
    assert record.fields["request_id"] == "31f863092ade1cb"
    span = record.field_span("request_id")
    assert span is not None
    assert line[slice(*span)] == "request_id=31f863092ade1cb"


@pytest.mark.parametrize(
    "line",
    [
        "",
        "plain text",
        '  record["message"] = record["message"].replace("\\t| ", "\\t\\| ")',
        "2026-10-02 09:38:28,970 INFO x",
        "2026-10-02T09:38:28.970+00:00 INFO no brackets",
    ],
)
def test_other_lines_are_not_lancelog(line):
    assert parse_lancelog(line) is None


@pytest.mark.parametrize(
    ("timestamp", "offset"),
    [("2026-10-02T09:38:28.970Z", timedelta(0)), ("2026-10-02T09:38:28.970+0200", timedelta(hours=2))],
)
def test_timestamp_offset_variants(timestamp, offset):
    record = parse_lancelog(f"{timestamp} DEBUG [-] m")
    assert record is not None and record.timestamp is not None
    assert record.timestamp.utcoffset() == offset


@pytest.mark.parametrize(("fraction", "microsecond"), [(".970", 970000), (".9701", 970100), (".97012", 970120)])
def test_timestamp_fraction_variants(fraction, microsecond):
    record = parse_lancelog(f"2026-10-02T09:38:28{fraction}+00:00 DEBUG [-] m")
    assert record is not None and record.timestamp is not None
    assert record.timestamp.microsecond == microsecond


DATA_LEVEL_LINE = HEADER.replace("INFO ", "DEBUG") + "Config.\t| level=TRACE message=other"


def test_header_level_and_message_win_over_data_keys():
    record = parse_lancelog(DATA_LEVEL_LINE)
    assert record is not None
    assert record.fields["level"] == "DEBUG"
    assert record.fields["message"] == "Config."
    assert record.field_span("level") == record.spans["level"]
    assert record.field_span("message") == record.spans["message"]
