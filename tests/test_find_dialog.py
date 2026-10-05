import asyncio

from textual.app import App, ComposeResult
from textual.widgets import Checkbox, Input

from toolong.find_dialog import FindDialog
from toolong.log_lines import SearchSuggester


class FindApp(App):
    def __init__(self) -> None:
        super().__init__()
        self.updates: list[FindDialog.Update] = []

    def compose(self) -> ComposeResult:
        yield FindDialog(SearchSuggester({}))

    def on_mount(self) -> None:
        self.query_one(FindDialog).add_class("visible")

    def on_find_dialog_update(self, event: FindDialog.Update) -> None:
        self.updates.append(event)


async def set_checkbox(app: App, pilot, selector: str, value: bool) -> None:
    app.query_one(selector, Checkbox).value = value
    await pilot.pause()


async def set_input(app: App, pilot, selector: str, value: str) -> None:
    app.query_one(selector, Input).value = value
    await pilot.pause()


def test_fields_mode_sends_the_field_query():
    async def scenario() -> None:
        app = FindApp()
        async with app.run_test() as pilot:
            await set_checkbox(app, pilot, "#fields", True)
            await set_input(app, pilot, "#find-fields", "level=ERROR")
            update = app.updates[-1]
            assert (update.find, update.fields, update.regex) == ("level=ERROR", True, False)

    asyncio.run(scenario())


def test_regex_mode_sends_the_regex_input():
    async def scenario() -> None:
        app = FindApp()
        async with app.run_test() as pilot:
            await set_checkbox(app, pilot, "#regex", True)
            await set_input(app, pilot, "#find-regex", "ab+c")
            update = app.updates[-1]
            assert (update.find, update.regex, update.fields) == ("ab+c", True, False)

    asyncio.run(scenario())


def test_regex_and_fields_are_exclusive_and_keep_the_query():
    async def scenario() -> None:
        app = FindApp()
        async with app.run_test() as pilot:
            dialog = app.query_one(FindDialog)
            await set_input(app, pilot, "#find-text", "x=1")
            await set_checkbox(app, pilot, "#regex", True)
            assert dialog.mode == "regex"
            assert app.query_one("#find-regex", Input).value == "x=1"
            await set_checkbox(app, pilot, "#fields", True)
            assert dialog.mode == "fields"
            assert app.query_one("#regex", Checkbox).value is False
            assert app.query_one("#find-fields", Input).value == "x=1"

    asyncio.run(scenario())
