import asyncio
import io

import pytest

from rich.console import Console
from rich.table import Table
from rich.text import Text
from textual.app import App, ComposeResult

import toolong.line_panel
from pilot_helpers import scanned_log_lines
from toolong.adr_0010 import parse_adr_0010
from toolong.ldap_dn import parse_dn
from toolong.line_panel import MAX_CONTAINER_LENGTH, LineDisplay, fields_table, value_text
from toolong.ui import UI

LINE = "2026-10-02T09:38:29.200+00:00 ERROR    [         -] Sync failed.\t| gitlab_project_id=211"


def render(table: Table) -> str:
    console = Console(width=120, record=True, file=io.StringIO())
    console.print(table)
    return console.export_text()


def test_fields_table_lists_timestamp_header_and_data_fields():
    record = parse_adr_0010(LINE)
    assert record is not None
    output = render(fields_table(record))
    for expected in ["timestamp", "2026-10-02T09:38:29.200000+00:00", "level", "ERROR", "message", "Sync failed.", "gitlab_project_id", "211"]:
        assert expected in output


def test_multiline_values_render_on_separate_lines():
    record = parse_adr_0010(
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


def test_line_display_shows_field_table_for_adr_0010_lines():
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


def test_fields_table_shows_header_level_and_data_level():
    record = parse_adr_0010(
        "2026-10-02T09:38:29.200+00:00 DEBUG    [         -] Config.\t| level=TRACE"
    )
    assert record is not None
    rows = [line.split() for line in render(fields_table(record)).splitlines()]
    assert ["level", "DEBUG"] in rows
    assert ["level", "TRACE"] in rows


def test_fields_table_shows_keys_verbatim():
    record = parse_adr_0010("2026-10-02T09:38:29.200+00:00 DEBUG    [-] C.\t| x[bold]y=1")
    assert record is not None
    assert "x[bold]y" in render(fields_table(record))


def test_line_display_splits_repr_newlines_in_adr_0010_messages():
    line = "2026-10-02T09:38:29.200+00:00 ERROR    [-] 'a\\nb'\t| k=v"

    async def scenario() -> None:
        app = PanelApp(line)
        async with app.run_test():
            assert len(app.query(".nl")) == 1
            assert len(app.query(".fields")) == 1

    asyncio.run(scenario())


DN_LINE = "2026-10-15T05:05:20.501296+02:00    DEBUG [         -] bind\t| " + r'dn="ou=foo\\3cbar\\3e \\2b 1,dc=cerbos,dc=dev"'


def styles_at(text: Text, index: int) -> list[str]:
    return [str(span.style) for span in text.spans if span.start <= index < span.end]


def test_dn_values_are_shown_decoded():
    assert value_text(r"ou=foo\3cbar\3e \2b 1,dc=cerbos,dc=dev").plain == "ou=foo<bar> + 1,dc=cerbos,dc=dev"


def test_dn_separators_are_styled_and_value_characters_are_not():
    text = value_text(r"ou=a\2bb+cn=c\2cd,dc=x")
    plain = text.plain
    assert plain == "ou=a+b+cn=c,d,dc=x"
    assert styles_at(text, plain.index("=")) == ["repr.attrib_equal"]
    assert styles_at(text, plain.index("+b")) == []
    assert styles_at(text, plain.index("+cn")) == ["repr.comma"]
    assert styles_at(text, plain.index(",d,")) == []
    assert styles_at(text, plain.index(",dc")) == ["repr.comma"]
    assert styles_at(text, plain.index("cn")) == ["repr.attrib_name"]


def test_control_characters_in_dn_values_are_shown_as_dim_escapes():
    text = value_text(r"cn=a\0ab,dc=x")
    assert text.plain == "cn=a\\nb,dc=x"
    assert styles_at(text, 4) == ["dim"]


def test_other_values_are_shown_unchanged():
    for value in ["(uid=a\\2ab)", "0.003416", 'Traceback:\n  x = "a\\b"', "cn=a\\3"]:
        text = value_text(value)
        assert text.plain == value
        assert text.spans == []


def test_fields_table_shows_dns_decoded():
    record = parse_adr_0010(DN_LINE)
    assert record is not None
    assert "ou=foo<bar> + 1,dc=cerbos,dc=dev" in render(fields_table(record))


def test_dns_are_detected_only_while_the_line_details_are_open(tmp_path, monkeypatch):
    path = tmp_path / "app.log"
    path.write_text(DN_LINE + "\n")
    checked: list[str] = []

    def counting_parse_dn(value: str):
        checked.append(value)
        return parse_dn(value)

    monkeypatch.setattr(toolong.line_panel, "parse_dn", counting_parse_dn)

    async def scenario() -> None:
        app = UI([str(path)])
        async with app.run_test(size=(160, 40)) as pilot:
            log_lines = await scanned_log_lines(pilot)
            log_lines.focus()
            await pilot.press("g", "enter")
            await pilot.pause()
            assert checked == []
            await pilot.press("enter")
            await pilot.pause()
            assert len(app.query(".fields")) == 1
            assert checked == [r"ou=foo\3cbar\3e \2b 1,dc=cerbos,dc=dev"]

    asyncio.run(scenario())


def test_single_attribute_values_keep_their_text():
    assert value_text("objectClass=sambaDomain").plain == "objectClass=sambaDomain"


LIST_VALUE = "['uid=alice,cn=users,dc=root', 'uid=bob,cn=users,dc=root']"
DICT_VALUE = (
    "{'foo': 'bar', 'bar': 123, 'dn1': 'uid=alice,cn=users,dc=root', 'dn2': 'uid=bob,cn=users,dc=root', "
    "'dns': ['uid=alice,cn=users,dc=root', 'uid=bob,cn=users,dc=root']}"
)


def test_dns_in_a_list_keep_the_list_text_and_get_colored_separators():
    text = value_text(LIST_VALUE)
    assert text.plain == LIST_VALUE
    assert styles_at(text, LIST_VALUE.index("uid=bob")) == ["repr.attrib_name"]
    assert styles_at(text, LIST_VALUE.index(", 'uid=bob")) == []


def test_dns_in_a_nested_dict_are_found_and_other_items_stay_plain():
    text = value_text(DICT_VALUE)
    assert text.plain == DICT_VALUE
    for dn_start in ("uid=alice,cn=users,dc=root', 'dn2", "uid=bob,cn=users,dc=root', 'dns", "uid=bob,cn=users,dc=root']"):
        assert styles_at(text, DICT_VALUE.index(dn_start)) == ["repr.attrib_name"]
    assert styles_at(text, DICT_VALUE.index("foo")) == []
    assert styles_at(text, DICT_VALUE.index("123")) == []


def test_escaped_dns_in_a_list_are_decoded_inside_their_quotes():
    assert value_text(r"['ou=foo\\3cbar\\3e \\2b 1,dc=x', 7]").plain == "['ou=foo<bar> + 1,dc=x', 7]"


def test_implicitly_concatenated_strings_are_shown_as_written():
    for value in ["['cn=a' 'b']", "['x' 'cn=a,dc=b']", "['cn=a' \"b\"]"]:
        assert value_text(value).plain == value
    assert value_text("['cn=a' 'b', 'cn=c\\\\2b']").plain == "['cn=a' 'b', 'cn=c+']"


def test_container_with_a_carriage_return_is_not_decoded():
    # Rich drops "\r" from any Text, so only the decoding is checked.
    assert value_text("['Tübingen',\r'cn=a\\\\2b,dc=b']").spans == []


def test_double_quotes_and_non_ascii_text_before_a_dn_are_kept():
    value = r"""('Tübingen', "cn=it's\\2b,dc=x")"""
    assert value_text(value).plain == """('Tübingen', "cn=it's+,dc=x")"""


@pytest.mark.parametrize(
    "value",
    [
        "(objectClass=*)",
        "(&(uid=a)(cn=b))",
        "['a', 'b c=d']",
        "{'a': 1}",
        "[x=1]",
        "['cn=a'",
        "[print('cn=a')]",
        "['cn=a', 'b'\n]",
        "[" * 1000 + "'cn=a'" + "]" * 1000,
        "['cn=a" + "a" * MAX_CONTAINER_LENGTH + "']",
    ],
)
def test_other_container_like_values_are_shown_unchanged(value):
    text = value_text(value)
    assert text.plain == value
    assert text.spans == []
