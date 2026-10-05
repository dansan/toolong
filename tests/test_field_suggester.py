import asyncio

from toolong.field_suggester import FieldIndex, FieldSuggester


def make_index() -> FieldIndex:
    index = FieldIndex()
    index.add({"level": "INFO", "message": "Start.", "gitlab_project_id": "211", "event": "sync done"})
    index.add({"level": "ERROR", "gitlab_project_id": "42"})
    return index


def suggest(value: str, index: FieldIndex | None = None) -> str | None:
    return asyncio.run(FieldSuggester(index or make_index()).get_suggestion(value))


def test_completes_key():
    assert suggest("gitlab_p") == "gitlab_project_id="


def test_completes_key_after_other_terms():
    assert suggest("level=INFO gitl") == "level=INFO gitlab_project_id="


def test_completes_most_recent_value():
    assert suggest("gitlab_project_id=") == "gitlab_project_id=42"


def test_completes_value_prefix():
    assert suggest("gitlab_project_id=2") == "gitlab_project_id=211"


def test_completes_value_after_not_equal():
    assert suggest("level!=E") == "level!=ERROR"


def test_quotes_values_that_need_it():
    assert suggest("event=") == 'event="sync done"'


def test_message_key_is_known_but_its_values_are_not_suggested():
    index = make_index()
    assert "message" in index.keys()
    assert suggest("message=", index) is None


def test_no_suggestion_inside_quoted_value():
    assert suggest('event="sy') is None


def test_no_suggestion_for_empty_input():
    assert suggest("") is None


def test_values_per_key_are_bounded_and_most_recent_first():
    index = FieldIndex()
    for number in range(60):
        index.add({"n": str(number)})
    assert len(index.values("n")) == FieldIndex.MAX_VALUES_PER_KEY
    assert index.values("n")[0] == "59"
