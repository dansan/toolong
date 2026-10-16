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
        "pid": 2407446,
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
    assert ast.literal_eval(export.text)["a"] == 2
    assert export.problems == ["Data key 'a' appears more than once; the last value was copied."]


def test_data_request_id_is_kept_next_to_the_shortened_header_one():
    export = export_line((HEADER + "request_id=31f863092ade1cb").encode(), as_json=False)
    assert export.problems == []
    data = ast.literal_eval(export.text)
    assert (data["_request_id"], data["request_id"]) == ("31f863092a", "31f863092ade1cb")


def test_line_without_data_exports_the_header():
    assert python_data(b"2026-10-15T05:05:20.501296+02:00    DEBUG [31f863092a] bind") == HEADER_DATA


def test_trailing_line_break_is_not_copied():
    assert python_data((HEADER + "a=1\r\n").encode())["a"] == 1


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


def test_numbers_and_booleans_are_copied_as_numbers_and_booleans():
    raw = (HEADER + "a=12 b=34.56 c=true d=false e=.5 f=7. g=-3 h=-0.25 i=-.5 j=0 k=0.5").encode()
    expected = {
        **{"a": 12, "b": 34.56, "c": True, "d": False, "e": 0.5, "f": 7.0},
        **{"g": -3, "h": -0.25, "i": -0.5, "j": 0, "k": 0.5},
    }
    python = python_data(raw)
    json_data = json.loads(export_line(raw, as_json=True).text)
    for key, value in expected.items():
        assert type(python[key]) is type(value) and python[key] == value
        assert type(json_data[key]) is type(value) and json_data[key] == value
    assert '"c": true, "d": false' in export_line(raw, as_json=True).text


def test_other_values_stay_strings():
    raw = (HEADER + 'a=+1 b=1.2.3 c=. d=1e5 e=True f=" 1" g=١ h= i=- j=--1 k=1-').encode()
    assert python_data(raw) == {
        **HEADER_DATA,
        **{"a": "+1", "b": "1.2.3", "c": ".", "d": "1e5", "e": "True", "f": " 1", "g": "١", "h": ""},
        **{"i": "-", "j": "--1", "k": "1-"},
    }


def test_numbers_with_leading_zeros_stay_strings():
    raw = (HEADER + "a=007 b=0755 c=-01 d=00.5 e=-00.5").encode()
    assert python_data(raw) == {
        **HEADER_DATA,
        **{"a": "007", "b": "0755", "c": "-01", "d": "00.5", "e": "-00.5"},
    }


def test_header_values_stay_strings():
    raw = b"2026-10-15T05:05:20.501296+02:00    DEBUG [1234567890] 42"
    assert python_data(raw) == {**HEADER_DATA, "_request_id": "1234567890", "_message": "42"}


def test_numbers_too_long_for_int_or_float_stay_strings():
    digits = "9" * 5000
    raw = (HEADER + f"a={digits} b={digits}.0").encode()
    data = json.loads(export_line(raw, as_json=True).text)
    assert (data["a"], data["b"]) == (digits, digits + ".0")
