import os

import pytest

from toolong.lancelog import parse_lancelog

SAMPLES = [path for path in os.environ.get("LANCELOG_SAMPLE_LOGS", "").split(os.pathsep) if path]


@pytest.mark.parametrize("path", SAMPLES)
def test_sample_records_parse_the_same_raw_and_tab_expanded(path):
    records = 0
    with open(path, encoding="utf-8") as file:
        for line in file:
            raw = parse_lancelog(line)
            if raw is None:
                continue
            records += 1
            assert raw.data_valid, line
            expanded = parse_lancelog(line.expandtabs(4))
            assert expanded is not None and expanded.fields == raw.fields, line
    assert records
