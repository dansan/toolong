import asyncio

from textual.widgets import Checkbox, Input

from pilot_helpers import scanned_log_lines
from toolong.find_dialog import FindDialog
from toolong.ui import UI

LINES = [
    "2026-10-02T09:38:28.970+00:00 INFO     [         -] Start.\t| _source=a:1",
    "2026-10-02T09:38:29.000+00:00 DEBUG    [         -] Page.\t| page=10 _source=a:2",
    "2026-10-02T09:38:29.100+00:00 DEBUG    [         -] Page.\t| page=1 _source=a:3",
    "2026-10-02T09:38:29.200+00:00 ERROR    [1234567890] Sync failed.\t| gitlab_project_id=211 _source=a:4",
]


async def find_fields(pilot, query: str) -> None:
    await pilot.press("slash")
    dialog = pilot.app.screen.query_one(FindDialog)
    dialog.query_one("#fields", Checkbox).value = True
    await pilot.pause()
    dialog.query_one("#find-fields", Input).value = query
    dialog.focus_input()
    await pilot.pause()


def test_field_search_moves_pointer_to_the_matching_line(tmp_path):
    path = tmp_path / "app.log"
    path.write_text("\n".join(LINES) + "\n")

    async def scenario() -> None:
        app = UI([str(path)])
        async with app.run_test(size=(160, 40)) as pilot:
            log_lines = await scanned_log_lines(pilot)
            await find_fields(pilot, "page=1")
            await pilot.press("down")
            await pilot.pause()
            assert log_lines.pointer_line == 2

    asyncio.run(scenario())


def test_field_highlight_on_line_longer_than_display_limit(tmp_path):
    line = (
        "2026-10-02T09:38:28.970+00:00 ERROR    [         -] Big.\t| blob="
        + "x" * 1500
        + " gitlab_project_id=211"
    )
    path = tmp_path / "long.log"
    path.write_text(line + "\n")

    async def scenario() -> None:
        app = UI([str(path)])
        async with app.run_test(size=(160, 40)) as pilot:
            log_lines = await scanned_log_lines(pilot)
            await find_fields(pilot, "level=ERROR gitlab_project_id=211")
            line_text, text, _ = log_lines.get_text(0, abbreviate=True, block=True)
            log_lines.highlight_find(text, line_text)
            filter_style = log_lines.get_component_rich_style("loglines--filter-highlight")
            assert any(span.style == filter_style for span in text.spans)
            assert all(str(span.style) != "dim" for span in text.spans)

    asyncio.run(scenario())
