from __future__ import annotations

from importlib.metadata import version
import os
import sys
from typing import IO

import click

from toolong.time_range import TimeRange, parse_time
from toolong.ui import UI


def child_argv(
    program: str,
    path: str,
    since: str | None,
    until: str | None,
    output_merge: str | None,
) -> list[str]:
    """Command line for the child process that shows the piped input saved in `path`."""
    argv = [program, path]
    if since is not None:
        argv += ["--since", since]
    if until is not None:
        argv += ["--until", until]
    if output_merge is not None:
        argv += ["-o", output_merge]
    return argv


def copy_until_eof(fileno: int, destination: IO[bytes]) -> None:
    while chunk := os.read(fileno, 1024 * 64):
        destination.write(chunk)


def stdin_is_tty() -> bool:
    return sys.__stdin__ is not None and sys.__stdin__.isatty()


def check_time(ctx: click.Context, param: click.Parameter, value: str | None) -> str | None:
    if value is not None:
        try:
            parse_time(value)
        except ValueError as error:
            raise click.BadParameter(str(error)) from None
    return value


@click.command()
@click.version_option(version("toolong"))
@click.argument("files", metavar="FILE1 FILE2", nargs=-1)
@click.option("-m", "--merge", is_flag=True, help="Merge files.")
@click.option(
    "-o",
    "--output-merge",
    metavar="PATH",
    nargs=1,
    help="Path to save merged or time-filtered lines (requires -m, --since or --until).",
)
@click.option(
    "--since",
    metavar="TIME",
    callback=check_time,
    help=(
        "Show only lines at or after TIME, an ISO 8601 date (YYYY-MM-DD) or date and time,"
        " e.g. 2026-10-02 or 2026-10-02T09:30. Without a UTC offset, TIME is local time."
    ),
)
@click.option(
    "--until",
    metavar="TIME",
    callback=check_time,
    help=(
        "Show only lines at or before TIME, in the same format as --since."
        " A date alone (YYYY-MM-DD) includes that whole day."
    ),
)
def run(
    files: list[str],
    merge: bool,
    output_merge: str | None,
    since: str | None,
    until: str | None,
) -> None:
    """View / tail / search log files."""
    try:
        time_range = TimeRange.from_strings(since, until)
    except ValueError as error:
        raise click.UsageError(str(error)) from None
    stdin_tty = stdin_is_tty()
    if not files and stdin_tty:
        ctx = click.get_current_context()
        click.echo(ctx.get_help())
        ctx.exit()
    if stdin_tty:
        try:
            ui = UI(files, merge=merge, save_merge=output_merge, time_range=time_range)
            ui.run()
        except Exception:
            pass
    else:
        import signal
        import selectors
        import subprocess
        import tempfile

        def request_exit(*args) -> None:
            """Don't write anything when a signal forces an error."""
            sys.stderr.write("^C")

        # Write piped data to a temporary file
        with tempfile.NamedTemporaryFile(
            mode="w+b", buffering=0, prefix="tl_"
        ) as temp_file:

            if time_range is not None:
                # The child scans the file once, without tailing, so it must be complete.
                sys.stderr.write("Reading piped input until it ends...\n")
                try:
                    copy_until_eof(sys.stdin.fileno(), temp_file)
                except KeyboardInterrupt:
                    sys.exit(130)

            signal.signal(signal.SIGINT, request_exit)
            signal.signal(signal.SIGTERM, request_exit)

            # Get input directly from /dev/tty to free up stdin
            with open("/dev/tty", "rb", buffering=0) as tty_stdin:
                # Launch a new process to render the UI
                with subprocess.Popen(
                    child_argv(sys.argv[0], temp_file.name, since, until, output_merge),
                    stdin=tty_stdin,
                    close_fds=True,
                    env={**os.environ, "TEXTUAL_ALLOW_SIGNALS": "1"},
                ) as process:
                    if time_range is not None:
                        process.wait()
                        return

                    # Current process copies from stdin to the temp file
                    selector = selectors.SelectSelector()
                    selector.register(sys.stdin.fileno(), selectors.EVENT_READ)

                    while process.poll() is None:
                        for _, event in selector.select(0.1):
                            if process.poll() is not None:
                                break
                            if event & selectors.EVENT_READ:
                                if line := os.read(sys.stdin.fileno(), 1024 * 64):
                                    temp_file.write(line)
                                else:
                                    break
