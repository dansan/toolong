"""Autocomplete field names and values in the find dialog's Fields mode."""

from __future__ import annotations

import re
from typing import Mapping

from textual.suggester import Suggester

from toolong.logfmt import encode_value

_LAST_TERM = re.compile(r'(?P<key>[^\s="!]*)(?:(?P<op>!=|=)(?P<value>[^\s"]*))?$')


class FieldIndex:
    """Keys and recently seen values of the Lancelog lines rendered so far."""

    MAX_VALUES_PER_KEY = 50
    MAX_VALUE_LENGTH = 80

    def __init__(self) -> None:
        self._values: dict[str, dict[str, None]] = {}

    def add(self, fields: Mapping[str, str]) -> None:
        for key, value in fields.items():
            values = self._values.setdefault(key, {})
            if key == "message" or len(value) > self.MAX_VALUE_LENGTH:
                continue
            values.pop(value, None)
            values[value] = None
            if len(values) > self.MAX_VALUES_PER_KEY:
                del values[next(iter(values))]

    def keys(self) -> list[str]:
        return sorted(self._values)

    def values(self, key: str) -> list[str]:
        """Most recently seen first."""
        return list(reversed(self._values.get(key, {})))


class FieldSuggester(Suggester):
    def __init__(self, index: FieldIndex) -> None:
        self.index = index
        super().__init__(use_cache=False, case_sensitive=True)

    async def get_suggestion(self, value: str) -> str | None:
        if value.count('"') % 2:
            return None
        match = _LAST_TERM.search(value)
        assert match is not None
        prefix = value[: match.start()]
        key = match["key"]
        if match["op"] is None:
            if not key:
                return None
            for candidate in self.index.keys():
                if candidate.startswith(key):
                    return f"{prefix}{candidate}="
            return None
        typed = match["value"]
        for candidate in self.index.values(key):
            encoded = encode_value(candidate)
            if encoded.startswith(typed) and encoded != typed:
                return f"{prefix}{key}{match['op']}{encoded}"
        return None
