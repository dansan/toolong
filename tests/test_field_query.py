import pytest

from toolong.field_query import FieldQuery, match_line, match_spans, parse_field_query

FIELDS = {
    "level": "ERROR",
    "request_id": "-",
    "message": "Sync failed.",
    "gitlab_project_id": "211",
    "event": "sync done",
    "ref_count": "1",
}
LINE = '2026-10-02T09:38:29.200+00:00 ERROR    [         -] Sync failed.\t| gitlab_project_id=211 event="sync done"'


def query(text: str) -> FieldQuery:
    parsed = parse_field_query(text)
    assert parsed is not None
    return parsed


def test_all_terms_must_match():
    assert query("level=ERROR gitlab_project_id=211").matches(FIELDS, case_sensitive=True)
    assert not query("level=ERROR gitlab_project_id=21").matches(FIELDS, case_sensitive=True)


def test_value_prefix_and_key_suffix_do_not_match():
    assert not query("gitlab_project_id=2").matches(FIELDS, case_sensitive=True)
    assert not query("count=1").matches(FIELDS, case_sensitive=True)


def test_not_equal_matches_other_values_and_missing_keys():
    assert query("level!=INFO").matches(FIELDS, case_sensitive=True)
    assert query("missing!=x").matches(FIELDS, case_sensitive=True)
    assert not query("level!=ERROR").matches(FIELDS, case_sensitive=True)


def test_quoted_values_are_decoded():
    assert query('event="sync done"').matches(FIELDS, case_sensitive=True)
    assert query(r'k="say \"hi\""').terms[0].value == 'say "hi"'


def test_case_sensitivity_applies_to_values_only():
    assert query("level=error").matches(FIELDS, case_sensitive=False)
    assert not query("level=error").matches(FIELDS, case_sensitive=True)
    assert not query("LEVEL=ERROR").matches(FIELDS, case_sensitive=False)


def test_empty_value_matches_only_present_empty_field():
    assert query("note=").matches({"note": ""}, case_sensitive=True)
    assert not query("note=").matches({}, case_sensitive=True)


@pytest.mark.parametrize("text", ["", "   "])
def test_empty_query_matches_every_record(text):
    assert query(text).matches({}, case_sensitive=True)


@pytest.mark.parametrize(
    "text", ["level", "level ERROR", "=x", "!=x", 'k="open', 'k=a"b', "level==ERROR", "a=b=c"]
)
def test_invalid_queries(text):
    assert parse_field_query(text) is None


def test_match_line_parses_lancelog_lines():
    assert match_line(query("gitlab_project_id=211"), LINE, case_sensitive=True)
    assert match_line(query("gitlab_project_id=211"), LINE.expandtabs(4), case_sensitive=True)


def test_match_line_rejects_other_lines():
    assert not match_line(query(""), "Traceback (most recent call last):", case_sensitive=True)


def test_could_match_requires_data_keys_of_equality_terms():
    assert not query("absent_key=1").could_match(LINE)
    assert query("level=ERROR absent!=1").could_match(LINE)


def test_match_spans_cover_matched_fields():
    spans = match_spans(query('level=ERROR event="sync done"'), LINE, case_sensitive=True)
    assert spans is not None
    assert [LINE[start:end] for start, end in spans] == ["ERROR", 'event="sync done"']


def test_match_spans_is_none_without_match():
    assert match_spans(query("level=INFO"), LINE, case_sensitive=True) is None


def test_header_level_wins_over_data_level():
    line = "2026-10-02T09:38:28.970+00:00 DEBUG    [         -] Config.\t| level=TRACE"
    assert match_line(query("level=DEBUG"), line, case_sensitive=True)
    assert not match_line(query("level=TRACE"), line, case_sensitive=True)


def test_value_with_equals_sign_must_be_quoted():
    assert query('a="b=c"').terms[0].value == "b=c"
