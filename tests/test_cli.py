import io
import os
import threading
import time

from click.testing import CliRunner

import toolong.cli
from toolong.cli import child_argv, copy_until_eof, run
from toolong.time_range import TimeRange, parse_timezone


def test_invalid_time_is_a_usage_error():
    result = CliRunner().invoke(run, ["--since", "yesterday", "x.log"])
    assert result.exit_code == 2
    assert "ISO 8601" in result.output
    assert "--since" in result.output
    assert "'yesterday'" in result.output


def test_invalid_until_names_the_option():
    result = CliRunner().invoke(run, ["--until", "tomorrow", "x.log"])
    assert result.exit_code == 2
    assert "--until" in result.output
    assert "'tomorrow'" in result.output


def test_since_after_until_is_a_usage_error():
    result = CliRunner().invoke(run, ["--since", "2026-10-03", "--until", "2026-10-02T12:00", "x.log"])
    assert result.exit_code == 2
    assert "after" in result.output


def test_child_argv():
    assert child_argv("tl", "/t/tl_1", None, None, None, None) == ["tl", "/t/tl_1"]
    assert child_argv("tl", "/t/tl_1", None, None, None, "UTC") == ["tl", "/t/tl_1", "--timezone", "UTC"]
    assert child_argv("tl", "/t/tl_1", "2026-10-02", "2026-10-03T08:00", "out.log", "UTC") == [
        "tl",
        "/t/tl_1",
        "--timezone",
        "UTC",
        "--since",
        "2026-10-02",
        "--until",
        "2026-10-03T08:00",
        "-o",
        "out.log",
    ]


def test_copy_until_eof_reads_a_slow_pipe_to_the_end():
    read_fd, write_fd = os.pipe()
    chunks = [f"2026-10-02T09:00:{second:02}.000+00:00 INFO line\n".encode() for second in range(20)]

    def slow_writer() -> None:
        with os.fdopen(write_fd, "wb", buffering=0) as pipe:
            for chunk in chunks:
                pipe.write(chunk)
                time.sleep(0.01)

    writer = threading.Thread(target=slow_writer)
    writer.start()
    destination = io.BytesIO()
    try:
        copy_until_eof(read_fd, destination)
    finally:
        os.close(read_fd)
        writer.join()
    assert destination.getvalue() == b"".join(chunks)


def test_run_passes_time_range_and_output_path_to_the_ui(monkeypatch):
    calls = []

    class RecordingUI:
        def __init__(self, files, **kwargs) -> None:
            calls.append((files, kwargs))

        def run(self) -> None:
            pass

    monkeypatch.setattr(toolong.cli, "UI", RecordingUI)
    monkeypatch.setattr(toolong.cli, "stdin_is_tty", lambda: True)
    result = CliRunner().invoke(
        run, ["--since", "2026-10-02", "--until", "2026-10-03", "-o", "out.log", "a.log"]
    )
    assert result.exit_code == 0, result.output
    [(files, kwargs)] = calls
    assert list(files) == ["a.log"]
    assert kwargs["save_merge"] == "out.log"
    assert isinstance(kwargs["time_range"], TimeRange)
    berlin = parse_timezone("Europe/Berlin")
    assert kwargs["timezone"] == berlin
    assert kwargs["time_range"] == TimeRange.from_strings("2026-10-02", "2026-10-03", berlin)


def test_run_passes_the_chosen_timezone_to_the_ui(monkeypatch):
    calls = []

    class RecordingUI:
        def __init__(self, files, **kwargs) -> None:
            calls.append(kwargs)

        def run(self) -> None:
            pass

    monkeypatch.setattr(toolong.cli, "UI", RecordingUI)
    monkeypatch.setattr(toolong.cli, "stdin_is_tty", lambda: True)
    result = CliRunner().invoke(run, ["--timezone", "UTC", "--since", "2026-10-02T09:00", "a.log"])
    assert result.exit_code == 0, result.output
    [kwargs] = calls
    assert kwargs["timezone"] == parse_timezone("UTC")
    assert kwargs["time_range"].since == TimeRange.from_strings("2026-10-02T09:00Z", None).since


def test_unknown_timezone_is_a_usage_error():
    result = CliRunner().invoke(run, ["--timezone", "Mars/Olympus", "x.log"])
    assert result.exit_code == 2
    assert "--timezone" in result.output
    assert "'Mars/Olympus'" in result.output


def test_unavailable_default_timezone_falls_back_to_local_time(monkeypatch):
    calls = []

    class RecordingUI:
        def __init__(self, files, **kwargs) -> None:
            calls.append(kwargs)

        def run(self) -> None:
            pass

    monkeypatch.setattr(toolong.cli, "UI", RecordingUI)
    monkeypatch.setattr(toolong.cli, "stdin_is_tty", lambda: True)
    monkeypatch.setattr(toolong.cli, "DEFAULT_TIMEZONE", "Mars/Olympus")
    result = CliRunner().invoke(run, ["a.log"])
    assert result.exit_code == 0, result.output
    assert "Mars/Olympus" in result.output
    assert calls[0]["timezone"] is None
