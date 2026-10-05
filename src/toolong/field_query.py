"""Find Lancelog lines by field: `key=value` and `key!=value` terms, all must match."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Mapping

from toolong.lancelog import HEADER_KEYS, parse_lancelog
from toolong.logfmt import unescape

_TERM = re.compile(
    r'\s*(?P<key>[^\s="!]+)(?P<op>!=|=)(?:"(?P<quoted>(?:[^"\\]|\\.)*)"|(?P<bare>[^\s"]*))(?=\s|$)'
)


@dataclass(frozen=True)
class Term:
    key: str
    negate: bool
    value: str

    def matches(self, fields: Mapping[str, str], case_sensitive: bool) -> bool:
        actual = fields.get(self.key)
        if actual is None:
            equal = False
        elif case_sensitive:
            equal = actual == self.value
        else:
            equal = actual.casefold() == self.value.casefold()
        return equal != self.negate


@dataclass(frozen=True)
class FieldQuery:
    terms: tuple[Term, ...]

    def matches(self, fields: Mapping[str, str], case_sensitive: bool) -> bool:
        return all(term.matches(fields, case_sensitive) for term in self.terms)

    def could_match(self, line: str) -> bool:
        """Cheap check before parsing: data keys of `=` terms must appear in the line."""
        return all(
            term.key in line
            for term in self.terms
            if not term.negate and term.key not in HEADER_KEYS
        )


@lru_cache(maxsize=64)
def parse_field_query(text: str) -> FieldQuery | None:
    """Parse a query, or return None if it is invalid. An empty query matches every record."""
    terms: list[Term] = []
    position = 0
    end = len(text.rstrip())
    while position < end:
        match = _TERM.match(text, position)
        if match is None:
            return None
        quoted = match["quoted"]
        value = match["bare"] if quoted is None else unescape(quoted)
        terms.append(Term(match["key"], match["op"] == "!=", value))
        position = match.end()
    return FieldQuery(tuple(terms))


def match_line(query: FieldQuery, line: str, case_sensitive: bool) -> bool:
    if not query.could_match(line):
        return False
    record = parse_lancelog(line)
    return record is not None and query.matches(record.fields, case_sensitive)


def match_spans(
    query: FieldQuery, line: str, case_sensitive: bool
) -> list[tuple[int, int]] | None:
    """Spans of the fields matched by `=` terms, or None if the line doesn't match."""
    record = parse_lancelog(line)
    if record is None or not query.matches(record.fields, case_sensitive):
        return None
    spans = []
    for term in query.terms:
        if not term.negate and (span := record.field_span(term.key)) is not None:
            spans.append(span)
    return spans
