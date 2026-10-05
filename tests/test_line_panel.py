import asyncio
import io

from rich.console import Console
from rich.table import Table
from rich.text import Text
from textual.app import App, ComposeResult

from toolong.lancelog import parse_lancelog
from toolong.line_panel import LineDisplay, fields_table

LINE = "2026-10-02T09:38:29.200+00:00 ERROR    [         -] Sync failed.\t| gitlab_project_id=211"


def render(table: Table) -> str:
    console = Console(width=120, record=True, file=io.StringIO())
    console.print(table)
    return console.export_text()


def test_fields_table_lists_timestamp_header_and_data_fields():
    record = parse_lancelog(LINE)
    assert record is not None
    output = render(fields_table(record))
    for expected in ["timestamp", "2026-10-02T09:38:29.200000+00:00", "level", "ERROR", "message", "Sync failed.", "gitlab_project_id", "211"]:
        assert expected in output


def test_multiline_values_render_on_separate_lines():
    record = parse_lancelog(
        '2026-10-02T09:38:29.200+00:00 ERROR    [         -] Boom.\t| _traceback="Traceback:\\n  File x\\nValueError: y"'
    )
    assert record is not None
    lines = [line.strip() for line in render(fields_table(record)).splitlines()]
    assert "File x" in lines
    assert "ValueError: y" in lines


class PanelApp(App):
    def __init__(self, line: str) -> None:
        super().__init__()
        self.line = line

    def compose(self) -> ComposeResult:
        yield LineDisplay(self.line, Text(self.line), None)


def test_line_display_shows_field_table_for_lancelog_lines():
    async def scenario() -> None:
        app = PanelApp(LINE)
        async with app.run_test():
            assert len(app.query(".fields")) == 1

    asyncio.run(scenario())


def test_line_display_has_no_field_table_for_other_lines():
    async def scenario() -> None:
        app = PanelApp("plain text")
        async with app.run_test():
            assert len(app.query(".fields")) == 0

    asyncio.run(scenario())
