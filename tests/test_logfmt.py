import pytest

from toolong.logfmt import LogfmtPair, encode_value, parse_pairs


def test_parse_bare_quoted_and_empty_values():
    assert parse_pairs('a=1 b="x y" c=') == (
        LogfmtPair("a", "1", 0, 3),
        LogfmtPair("b", "x y", 4, 11),
        LogfmtPair("c", "", 12, 14),
    )


def test_offset_is_added_to_positions():
    assert parse_pairs("k=v", offset=10) == (LogfmtPair("k", "v", 10, 13),)


def test_quoted_value_escapes_are_decoded():
    data = r'tb="line 1\nline 2" q="say \"hi\"" path="C:\\my tmp" bell="\u0007"'
    pairs = parse_pairs(data)
    assert pairs is not None
    assert [pair.value for pair in pairs] == [
        "line 1\nline 2",
        'say "hi"',
        "C:\\my tmp",
        "\x07",
    ]


def test_backslash_in_bare_value_is_literal():
    pairs = parse_pairs(r"re=a\d")
    assert pairs is not None
    assert pairs[0].value == "a\\d"


@pytest.mark.parametrize("data", ["", "   "])
def test_empty_data_has_no_pairs(data):
    assert parse_pairs(data) == ()


@pytest.mark.parametrize("data", ['a="unterminated', "novalue", "a=1b=2", 'a=x"y', "=v"])
def test_malformed_data_is_rejected(data):
    assert parse_pairs(data) is None


@pytest.mark.parametrize(
    ("value", "encoded"),
    [
        ("plain", "plain"),
        ("", ""),
        ("two words", '"two words"'),
        ("a=b", '"a=b"'),
        ('say "hi"', r'"say \"hi\""'),
        ("C:\\tmp", "C:\\tmp"),
        ("C:\\my tmp", r'"C:\\my tmp"'),
        ("l1\nl2", r'"l1\nl2"'),
        ("\x07", r'"\u0007"'),
    ],
)
def test_encode_value_quotes_like_logfmter(value, encoded):
    assert encode_value(value) == encoded


@pytest.mark.parametrize("value", ["two words", 'say "hi"', "C:\\my tmp", "l1\nl2\tt", "\x07"])
def test_encoded_values_decode_to_the_original(value):
    pairs = parse_pairs(f"k={encode_value(value)}")
    assert pairs is not None
    assert pairs[0].value == value
