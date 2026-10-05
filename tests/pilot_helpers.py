from textual.pilot import Pilot

from toolong.log_lines import LogLines


async def scanned_log_lines(pilot: Pilot) -> LogLines:
    """Wait until the first log view has finished scanning its file(s)."""
    for _ in range(200):
        await pilot.pause(0.05)
        found = pilot.app.screen.query(LogLines)
        if found and not found.first().has_class("-scanning"):
            await pilot.pause()
            return found.first()
    raise AssertionError("log file was not scanned")
