from __future__ import annotations
import ast
from datetime import datetime
import json
import re

from rich import box
from rich.json import JSON
from rich.table import Table
from rich.text import Text

from textual.app import ComposeResult
from textual.containers import ScrollableContainer

from textual.widget import Widget
from textual.widgets import Label, Static

from toolong.lancelog import HEADER_KEYS, LancelogRecord, parse_lancelog
from toolong.ldap_dn import Ava, parse_dn

_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
# Longer list, tuple, set or dict values aren't parsed, so a huge value can't slow down the line details.
MAX_CONTAINER_LENGTH = 16384
_STRING_QUOTE = re.compile("[A-Za-z]*('''|\"\"\"|'|\")")


def fields_table(record: LancelogRecord) -> Table:
    table = Table(box=box.SIMPLE_HEAD)
    table.add_column("Field", style="repr.attrib_name", no_wrap=True)
    table.add_column("Value", overflow="fold")
    if record.timestamp is not None:
        table.add_row("timestamp", record.timestamp.isoformat())
    for key in HEADER_KEYS:
        table.add_row(key, Text(record.fields[key]))
    for pair in record.pairs:
        table.add_row(Text(pair.key), value_text(pair.value))
    return table


def value_text(value: str) -> Text:
    """Show DNs, alone or in a Python list, tuple, set or dict literal, with decoded values."""
    rdns = parse_dn(value)
    if rdns is not None:
        return dn_text(rdns)
    if value.startswith(("[", "(", "{")) and "=" in value:
        text = _container_text(value)
        if text is not None:
            return text
    return Text(value)


def dn_text(rdns: list[list[Ava]]) -> Text:
    """Decoded values, with colored separators to tell them from value characters."""
    text = Text()
    for rdn_index, rdn in enumerate(rdns):
        if rdn_index:
            text.append(",", "repr.comma")
        for ava_index, ava in enumerate(rdn):
            if ava_index:
                text.append("+", "repr.comma")
            text.append(ava.type, "repr.attrib_name")
            text.append("=", "repr.attrib_equal")
            _append_visibly(text, ava.value)
    return text


def _container_text(value: str) -> Text | None:
    """Show a Python literal as written, with its DN strings decoded, or return None if it has none."""
    if len(value) > MAX_CONTAINER_LENGTH or "\n" in value:
        return None
    try:
        source = value.encode("utf-8")
        tree = ast.parse(value, mode="eval")
        ast.literal_eval(tree)
    except (SyntaxError, ValueError, TypeError, MemoryError, RecursionError, UnicodeEncodeError):
        return None
    dns: list[tuple[int, int, list[list[Ava]]]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.end_col_offset is not None:
            rdns = parse_dn(node.value)
            if rdns is not None:
                # Column offsets count UTF-8 bytes.
                dns.append((node.col_offset, node.end_col_offset, rdns))
    if not dns:
        return None
    text = Text()
    position = 0
    for start, end, rdns in sorted(dns, key=lambda dn: dn[0]):
        quote = _STRING_QUOTE.match(source[start:end].decode("utf-8"))
        assert quote is not None
        text.append(source[position:start].decode("utf-8"))
        text.append(quote[0])
        text.append_text(dn_text(rdns))
        text.append(quote[1])
        position = end
    text.append(source[position:].decode("utf-8"))
    return text


def _append_visibly(text: Text, value: str) -> None:
    """Append `value` with control characters as dim Python escapes, such as \\n."""
    position = 0
    for match in _CONTROL.finditer(value):
        text.append(value[position : match.start()])
        text.append(repr(match[0])[1:-1], "dim")
        position = match.end()
    text.append(value[position:])


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

        if "\\n" in self.text.plain:
            lines = self.text.split("\\n")
            text = Text("\n", no_wrap=True).join(lines)
            yield Label(text, classes="nl")
        else:
            yield Label(self.text)

        record = parse_lancelog(self.line)
        if record is not None:
            yield Static(fields_table(record), classes="fields")


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
