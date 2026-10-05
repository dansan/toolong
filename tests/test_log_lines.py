import asyncio

from pilot_helpers import scanned_log_lines
from toolong.ui import UI

LINES = [
    "2026-10-02T09:38:28.970+00:00 INFO     [         -] Start.\t| _source=a:1",
    "2026-10-02T09:38:29.000+00:00 DEBUG    [         -] Page.\t| page=10 _source=a:2",
    "2026-10-02T09:38:29.100+00:00 DEBUG    [         -] Page.\t| page=1 _source=a:3",
]


def test_regex_find_matches_in_the_middle_of_a_line(tmp_path):
    path = tmp_path / "app.log"
    path.write_text("\n".join(LINES) + "\n")

    async def scenario() -> None:
        app = UI([str(path)])
        async with app.run_test(size=(160, 40)) as pilot:
            log_lines = await scanned_log_lines(pilot)
            log_lines.regex = True
            log_lines.find = r"page=1\b"
            assert log_lines.check_match(LINES[2])
            assert not log_lines.check_match(LINES[1])

    asyncio.run(scenario())


def test_anchored_regex_find_matches_raw_lines(tmp_path):
    path = tmp_path / "app.log"
    path.write_text("\n".join(LINES) + "\n")

    async def scenario() -> None:
        app = UI([str(path)])
        async with app.run_test(size=(160, 40)) as pilot:
            log_lines = await scanned_log_lines(pilot)
            log_lines.show_find = True
            log_lines.regex = True
            log_lines.find = "^2026-10-02T09:38:29.100"
            log_lines.advance_search(1)
            assert log_lines.pointer_line == 2

    asyncio.run(scenario())


def test_find_skips_blank_lines(tmp_path):
    path = tmp_path / "blank.log"
    path.write_text("first\n\nneedle\n")

    async def scenario() -> None:
        app = UI([str(path)])
        async with app.run_test(size=(160, 40)) as pilot:
            log_lines = await scanned_log_lines(pilot)
            log_lines.show_find = True
            log_lines.find = "needle"
            log_lines.advance_search(1)
            assert log_lines.pointer_line == 2

    asyncio.run(scenario())
