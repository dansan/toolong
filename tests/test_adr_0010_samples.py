import os

import pytest

from toolong.adr_0010 import parse_adr_0010

SAMPLES = [path for path in os.environ.get("ADR_0010_SAMPLE_LOGS", "").split(os.pathsep) if path]


@pytest.mark.parametrize("path", SAMPLES)
def test_sample_records_parse_the_same_raw_and_tab_expanded(path):
    records = 0
    with open(path, encoding="utf-8") as file:
        for line in file:
            raw = parse_adr_0010(line)
            if raw is None:
                continue
            records += 1
            assert raw.data_valid, line
            expanded = parse_adr_0010(line.expandtabs(4))
            assert expanded is not None and expanded.fields == raw.fields, line
    assert records
