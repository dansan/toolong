import ast
import json

from toolong.record_export import Export, export_line

HEADER = "2026-10-15T05:05:20.501296+02:00    DEBUG [31f863092a] bind\t| "
LINE = (HEADER + 'pid=2407446 binddn="cn=admin,dc=cerbos,dc=dev" ' + r'dn="ou=foo\\3cbar\\3e \\2b 1,dc=cerbos,dc=dev"').encode()
HEADER_DATA = {
    "_timestamp": "2026-10-15T05:05:20.501296+02:00",
    "_level": "DEBUG",
    "_request_id": "31f863092a",
    "_message": "bind",
}


def python_data(raw: bytes) -> dict:
    export = export_line(raw, as_json=False)
    assert export.text is not None
    return ast.literal_eval(export.text)


def test_python_export_is_a_one_line_dict_literal_of_header_and_logfmt_decoded_data():
    export = export_line(LINE, as_json=False)
    assert export.problems == []
    assert "\n" not in export.text
    assert ast.literal_eval(export.text) == {
        **HEADER_DATA,
        "pid": "2407446",
        "binddn": "cn=admin,dc=cerbos,dc=dev",
        "dn": r"ou=foo\3cbar\3e \2b 1,dc=cerbos,dc=dev",
    }


def test_json_export_loads_to_the_same_dict_as_the_python_export():
    export = export_line(LINE, as_json=True)
    assert export.problems == []
    assert "\n" not in export.text
    assert json.loads(export.text) == python_data(LINE)


def test_json_keeps_the_key_order_and_writes_non_ascii_characters_as_they_are():
    export = export_line((HEADER + "city=Tübingen").encode(), as_json=True)
    assert export.text == (
        '{"_timestamp": "2026-10-15T05:05:20.501296+02:00", "_level": "DEBUG", '
        '"_request_id": "31f863092a", "_message": "bind", "city": "Tübingen"}'
    )


def test_json_escapes_lone_surrogates_so_the_text_can_be_encoded_as_utf8():
    export = export_line((HEADER + r's="\ud800"').encode(), as_json=True)
    export.text.encode("utf-8")
    assert json.loads(export.text)["s"] == "\ud800"


def test_quotes_newlines_and_backslashes_survive_both_formats():
    raw = (HEADER + r'''v="a \"q\" 'x'\nb\\c"''').encode()
    expected = "a \"q\" 'x'\nb\\c"
    assert python_data(raw)["v"] == expected
    assert json.loads(export_line(raw, as_json=True).text)["v"] == expected


def test_data_key_with_a_header_name_replaces_the_header_value_with_a_warning():
    export = export_line((HEADER + "_level=TRACE").encode(), as_json=False)
    assert ast.literal_eval(export.text)["_level"] == "TRACE"
    assert export.problems == ["Data key '_level' replaced the header value of the same name."]


def test_repeated_data_key_copies_the_last_value_with_a_warning():
    export = export_line((HEADER + "a=1 a=2").encode(), as_json=False)
    assert ast.literal_eval(export.text)["a"] == "2"
    assert export.problems == ["Data key 'a' appears more than once; the last value was copied."]


def test_data_request_id_is_kept_next_to_the_shortened_header_one():
    export = export_line((HEADER + "request_id=31f863092ade1cb").encode(), as_json=False)
    assert export.problems == []
    data = ast.literal_eval(export.text)
    assert (data["_request_id"], data["request_id"]) == ("31f863092a", "31f863092ade1cb")


def test_line_without_data_exports_the_header():
    assert python_data(b"2026-10-15T05:05:20.501296+02:00    DEBUG [31f863092a] bind") == HEADER_DATA


def test_trailing_line_break_is_not_copied():
    assert python_data((HEADER + "a=1\r\n").encode())["a"] == "1"


def test_other_lines_and_invalid_logfmt_copy_nothing():
    assert export_line(b"plain text", as_json=False) == Export(
        None, ["This line isn't an ADR 0010 record. Nothing was copied."]
    )
    assert export_line((HEADER + 'a="open').encode(), as_json=True) == Export(
        None, ["The data after | isn't valid logfmt. Nothing was copied."]
    )


def test_invalid_utf8_is_copied_as_replacement_characters_with_a_warning():
    export = export_line((HEADER + "a=x").encode() + b"\xff", as_json=True)
    assert json.loads(export.text)["a"] == "x�"
    assert export.problems == ["The line isn't valid UTF-8; invalid bytes were copied as �."]


def test_tabs_in_the_message_are_copied_as_tabs():
    raw = b"2026-10-15T05:05:20.501296+02:00    DEBUG [31f863092a] a\tb\t| k=v"
    assert python_data(raw)["_message"] == "a\tb"


def test_json_escapes_unicode_line_separators_so_it_stays_one_line():
    export = export_line((HEADER + 'v="a\u2028b\u2029c\u0085d"').encode(), as_json=True)
    assert len(export.text.splitlines()) == 1
    assert json.loads(export.text)["v"] == "a\u2028b\u2029c\u0085d"
