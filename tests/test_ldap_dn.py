import pytest

from toolong.ldap_dn import MAX_DN_LENGTH, Ava, parse_dn

UCS_OBJECT_DN = r"uid=user1,cn=user (Tübingen) \\\\ Bremen,ou=Foo\3Cbar\3E \2B 1,dc=cerbos,dc=dev"
AD_OBJECT_DN = r"cn=user1,cn=user (Tübingen) \\\\ Bremen,ou=Foo\<bar\> \+ 1,DC=cerbos,DC=dev"


def test_hex_escapes_are_decoded():
    assert parse_dn(r"ou=foo\3cbar\3e \2b 1,dc=cerbos,dc=dev") == [
        [Ava("ou", "foo<bar> + 1")],
        [Ava("dc", "cerbos")],
        [Ava("dc", "dev")],
    ]


def test_upper_case_hex_escapes_and_character_escapes_decode_the_same():
    assert parse_dn(r"ou=Foo\3Cbar\3E \2B 1") == parse_dn(r"ou=Foo\<bar\> \+ 1") == [[Ava("ou", "Foo<bar> + 1")]]


def test_hex_escaped_and_raw_utf8_decode_the_same():
    assert parse_dn(r"cn=J\c3\bcrgen") == parse_dn("cn=Jürgen") == [[Ava("cn", "Jürgen")]]


def test_escaped_backslashes_decode_to_backslashes():
    assert parse_dn(UCS_OBJECT_DN)[1] == [Ava("cn", "user (Tübingen) \\\\ Bremen")]


def test_multi_valued_rdns_split_at_unescaped_plus():
    assert parse_dn("cn=a+uid=b,dc=x") == [[Ava("cn", "a"), Ava("uid", "b")], [Ava("dc", "x")]]


def test_escaped_leading_and_trailing_spaces_and_leading_sharp():
    assert parse_dn(r"cn=\ a\ ,ou=\#b") == [[Ava("cn", " a ")], [Ava("ou", "#b")]]


def test_escaped_control_characters_are_decoded():
    assert parse_dn(r"cn=a\0ab") == [[Ava("cn", "a\nb")]]


def test_numeric_oid_types_and_hex_string_values_are_kept():
    assert parse_dn("2.5.4.3=#04024869,dc=x") == [[Ava("2.5.4.3", "#04024869")], [Ava("dc", "x")]]


def test_empty_value():
    assert parse_dn("cn=,dc=x") == [[Ava("cn", "")], [Ava("dc", "x")]]


@pytest.mark.parametrize(
    "text",
    [
        "",
        "plain text",
        "0.003416",
        "(objectClass=*)",
        'Traceback (most recent call last):\n  File "x", line 1\n    a = b\\c',
        "cn=a,",
        "cn=a,,dc=x",
        "=a",
        "cn=a,dc",
        "cn= a",
        "cn=a ",
        r"cn=a\\ ",
        "cn=#zz",
        "cn=#04x",
        'cn=a"b',
        "cn=a;b",
        "cn=a<b",
        "cn=a\nb",
        "cn=a\\",
        r"cn=a\x",
        r"cn=\ff",
        "cn=\ud800",
        "cn=" + "a" * MAX_DN_LENGTH,
    ],
)
def test_other_text_is_not_a_dn(text):
    assert parse_dn(text) is None


@pytest.mark.parametrize(
    "dn",
    [
        UCS_OBJECT_DN,
        AD_OBJECT_DN,
        r"ou=foo\3cbar\3e \2b 1,dc=cerbos,dc=dev",
        r"cn=\ a\ ,ou=\#b",
        r"cn=q\22uote\3b\3d\2c,dc=x",
        "cn=a+uid=b,dc=x",
        r"cn=J\c3\bcrgen,dc=x",
        r"cn=a\0ab",
        "objectClass=sambaDomain",
    ],
)
def test_decoded_values_match_python_ldap(dn):
    python_ldap_dn = pytest.importorskip("ldap.dn")
    expected = [[Ava(type, value) for type, value, _ in rdn] for rdn in python_ldap_dn.str2dn(dn)]
    assert parse_dn(dn) == expected
