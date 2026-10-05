from __future__ import annotations
from datetime import datetime
import json

from rich import box
from rich.json import JSON
from rich.table import Table
from rich.text import Text

from textual.app import ComposeResult
from textual.containers import ScrollableContainer

from textual.widget import Widget
from textual.widgets import Label, Static

from toolong.lancelog import HEADER_KEYS, LancelogRecord, parse_lancelog


def fields_table(record: LancelogRecord) -> Table:
    table = Table(box=box.SIMPLE_HEAD)
    table.add_column("Field", style="repr.attrib_name", no_wrap=True)
    table.add_column("Value", overflow="fold")
    if record.timestamp is not None:
        table.add_row("timestamp", record.timestamp.isoformat())
    for key in HEADER_KEYS:
        table.add_row(key, Text(record.fields[key]))
    for pair in record.pairs:
        table.add_row(Text(pair.key), Text(pair.value))
    return table


class LineDisplay(Widget):
    DEFAULT_CSS = """
    LineDisplay {        
        padding: 0 1;
        margin: 1 0;
        width: auto;
        height: auto;        
        Label {
            width: 1fr;
        }  
        .json {
            width: auto;        
        }
        .fields {
            width: auto;
        }
        .nl {
            width: auto;
        }  
    }
    """

    def __init__(self, line: str, text: Text, timestamp: datetime | None) -> None:
        self.line = line
        self.text = text
        self.timestamp = timestamp
        super().__init__()

    def compose(self) -> ComposeResult:
        try:
            json_data = json.loads(self.line)
        except Exception:
            pass
        else:
            yield Static(JSON.from_data(json_data), expand=True, classes="json")
            return

        record = parse_lancelog(self.line)
        if record is not None:
            yield Label(self.text)
            yield Static(fields_table(record), classes="fields")
            return

        if "\\n" in self.text.plain:
            lines = self.text.split("\\n")
            text = Text("\n", no_wrap=True).join(lines)
            yield Label(text, classes="nl")
        else:
            yield Label(self.text)


class LinePanel(ScrollableContainer):
    DEFAULT_CSS = """
    LinePanel {
        background: $panel;        
        overflow-y: auto;
        overflow-x: auto;
        border: blank transparent;                
        scrollbar-gutter: stable;
        &:focus {
            border: heavy $accent;
        }
    }
    """

    async def update(self, line: str, text: Text, timestamp: datetime | None) -> None:
        with self.app.batch_update():
            await self.query(LineDisplay).remove()
            await self.mount(LineDisplay(line, text, timestamp))
