import asyncio

import pytest
from textual.widgets import Input

import toolong.ui
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


def test_navigate_skips_naive_timestamps_in_a_file_with_aware_ones(tmp_path):
    path = tmp_path / "mixed.log"
    path.write_text(
        "2026-10-02T09:38:00.000+00:00 INFO     [-] aware\n"
        "2026-10-02 09:38:29,100 INFO naive\n"
        "2026-10-02T09:39:30.000+00:00 INFO     [-] aware\n"
    )

    async def scenario() -> None:
        app = UI([str(path)])
        async with app.run_test(size=(160, 40)) as pilot:
            log_lines = await scanned_log_lines(pilot)
            log_lines.focus()
            await pilot.press("m")
            await pilot.pause()
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


def test_g_scrolls_to_the_top_and_capital_g_to_the_end(tmp_path):
    path = tmp_path / "long.log"
    path.write_text("".join(f"line {number}\n" for number in range(200)))

    async def scenario() -> None:
        app = UI([str(path)])
        async with app.run_test(size=(160, 40)) as pilot:
            log_lines = await scanned_log_lines(pilot)
            log_lines.focus()
            await pilot.press("G")
            await pilot.pause()
            assert log_lines.scroll_offset.y == log_lines.max_scroll_y > 0
            await pilot.press("g")
            await pilot.pause()
            assert log_lines.scroll_offset.y == 0

    asyncio.run(scenario())


def test_g_and_capital_g_move_the_pointer_to_the_first_and_last_line(tmp_path):
    path = tmp_path / "long.log"
    path.write_text("".join(f"line {number}\n" for number in range(200)))

    async def scenario() -> None:
        app = UI([str(path)])
        async with app.run_test(size=(160, 40)) as pilot:
            log_lines = await scanned_log_lines(pilot)
            log_lines.focus()
            await pilot.press("enter")
            await pilot.press("G")
            await pilot.pause()
            assert log_lines.pointer_line == log_lines.line_count - 1
            await pilot.press("g")
            await pilot.pause()
            assert log_lines.pointer_line == 0

    asyncio.run(scenario())


def test_tail_scrolls_to_lines_that_arrived_while_not_tailing(tmp_path):
    path = tmp_path / "growing.log"
    path.write_text("".join(f"line {number}\n" for number in range(100)))

    async def scenario() -> None:
        app = UI([str(path)])
        async with app.run_test(size=(160, 40)) as pilot:
            log_lines = await scanned_log_lines(pilot)
            log_lines.focus()
            await pilot.press("g")
            await pilot.pause()
            assert not log_lines.tail
            with path.open("a") as log:
                log.write("".join(f"new {number}\n" for number in range(50)))
            for _ in range(40):
                await pilot.pause(0.05)
                if len(log_lines._line_breaks[log_lines.log_file]) == 150:
                    break
            await pilot.press("ctrl+t")
            await pilot.pause()
            assert log_lines.tail
            assert log_lines.line_count == 151
            assert log_lines.scroll_offset.y == log_lines.line_count - log_lines.scrollable_content_region.height

    asyncio.run(scenario())


def test_y_copies_the_pointer_line_to_the_clipboard(tmp_path):
    path = tmp_path / "app.log"
    path.write_text("first line\nsecond line\n")

    async def scenario() -> None:
        app = UI([str(path)])
        copied: list[str] = []
        app.copy_to_clipboard = copied.append
        async with app.run_test(size=(160, 40)) as pilot:
            log_lines = await scanned_log_lines(pilot)
            log_lines.focus()
            await pilot.press("g", "enter")
            assert log_lines.pointer_line == 0
            await pilot.press("y")
            await pilot.pause()
            assert copied == ["first line"]

    asyncio.run(scenario())


def test_y_without_pointer_copies_nothing(tmp_path):
    path = tmp_path / "app.log"
    path.write_text("\n".join(LINES) + "\n")

    async def scenario() -> None:
        app = UI([str(path)])
        copied: list[str] = []
        app.copy_to_clipboard = copied.append
        async with app.run_test(size=(160, 40)) as pilot:
            log_lines = await scanned_log_lines(pilot)
            log_lines.focus()
            await pilot.press("y")
            await pilot.pause()
            assert copied == []

    asyncio.run(scenario())


def test_y_is_typed_into_find_and_does_not_copy_from_go_to(tmp_path):
    path = tmp_path / "app.log"
    path.write_text("\n".join(LINES) + "\n")

    async def scenario() -> None:
        app = UI([str(path)])
        copied: list[str] = []
        app.copy_to_clipboard = copied.append
        async with app.run_test(size=(160, 40)) as pilot:
            log_lines = await scanned_log_lines(pilot)
            log_lines.focus()
            await pilot.press("enter", "ctrl+f", "y")
            await pilot.pause()
            assert app.screen.query_one("#find-text", Input).value == "y"
            await pilot.press("escape")
            log_lines.focus()
            await pilot.press("ctrl+g", "y")
            await pilot.pause()
            assert isinstance(app.focused, Input)
            assert copied == []

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("copied_locally", "message"),
    [(True, "Copied to the clipboard."), (False, "Sent to the terminal's clipboard (OSC 52).")],
)
def test_y_also_copies_with_local_tools_and_says_how(tmp_path, monkeypatch, copied_locally, message):
    path = tmp_path / "app.log"
    path.write_text("first line\nsecond line\n")
    local_copies: list[str] = []

    def copy_with_local_tools(text: str) -> bool:
        local_copies.append(text)
        return copied_locally

    monkeypatch.setattr(toolong.ui, "copy_with_local_tools", copy_with_local_tools)

    async def scenario() -> None:
        app = UI([str(path)])
        notifications: list[str] = []
        app.notify = lambda message, **kwargs: notifications.append(message)
        async with app.run_test(size=(160, 40)) as pilot:
            log_lines = await scanned_log_lines(pilot)
            log_lines.focus()
            await pilot.press("g", "enter", "y")
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert local_copies == ["first line"]
            assert notifications == [message]

    asyncio.run(scenario())
