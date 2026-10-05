from click.testing import CliRunner

from toolong.cli import run, time_range_args


def test_invalid_time_is_a_usage_error():
    result = CliRunner().invoke(run, ["--since", "yesterday", "x.log"])
    assert result.exit_code == 2
    assert "ISO 8601" in result.output


def test_since_after_until_is_a_usage_error():
    result = CliRunner().invoke(run, ["--since", "2026-10-03", "--until", "2026-10-02T12:00", "x.log"])
    assert result.exit_code == 2
    assert "after" in result.output


def test_time_range_args():
    assert time_range_args(None, None) == []
    assert time_range_args("2026-10-02", None) == ["--since", "2026-10-02"]
    assert time_range_args("2026-10-02", "2026-10-03T08:00") == [
        "--since",
        "2026-10-02",
        "--until",
        "2026-10-03T08:00",
    ]
