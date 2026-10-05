from __future__ import annotations

from importlib.metadata import version
import os
import sys

import click

from toolong.time_range import TimeRange
from toolong.ui import UI


def time_range_args(since: str | None, until: str | None) -> list[str]:
    """Time range options for the child process that shows piped input."""
    args: list[str] = []
    if since is not None:
        args += ["--since", since]
    if until is not None:
        args += ["--until", until]
    return args


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
    help=(
        "Show only lines at or after TIME, an ISO 8601 date or date and time,"
        " e.g. 2026-10-02 or 2026-10-02T09:30. Without a UTC offset, TIME is local time."
    ),
)
@click.option(
    "--until",
    metavar="TIME",
    help="Show only lines at or before TIME. A date without a time includes that whole day.",
)
def run(
    files: list[str],
    merge: bool,
    output_merge: str,
    since: str | None,
    until: str | None,
) -> None:
    """View / tail / search log files."""
    try:
        time_range = TimeRange.from_strings(since, until)
    except ValueError as error:
        raise click.UsageError(str(error)) from None
    stdin_tty = sys.__stdin__.isatty()
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

        signal.signal(signal.SIGINT, request_exit)
        signal.signal(signal.SIGTERM, request_exit)

        # Write piped data to a temporary file
        with tempfile.NamedTemporaryFile(
            mode="w+b", buffering=0, prefix="tl_"
        ) as temp_file:

            # Get input directly from /dev/tty to free up stdin
            with open("/dev/tty", "rb", buffering=0) as tty_stdin:
                # Launch a new process to render the UI
                with subprocess.Popen(
                    [sys.argv[0], temp_file.name, *time_range_args(since, until)],
                    stdin=tty_stdin,
                    close_fds=True,
                    env={**os.environ, "TEXTUAL_ALLOW_SIGNALS": "1"},
                ) as process:

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
