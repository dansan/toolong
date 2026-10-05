from __future__ import annotations

from dataclasses import dataclass
import re

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.suggester import Suggester
from textual.validation import Validator, ValidationResult
from textual.widget import Widget
from textual.widgets import Input, Checkbox

from toolong.field_query import parse_field_query


class Regex(Validator):
    def validate(self, value: str) -> ValidationResult:
        """Check a string is equal to its reverse."""
        try:
            re.compile(value)
        except Exception:
            return self.failure("Invalid regex")
        else:
            return self.success()


class FieldQueryValidator(Validator):
    def validate(self, value: str) -> ValidationResult:
        if parse_field_query(value) is None:
            return self.failure("Invalid field query")
        return self.success()


class FindDialog(Widget, can_focus_children=True):
    DEFAULT_CSS = """
    FindDialog {
        layout: horizontal;
        dock: top; 
        padding-top: 1;                       
        width: 1fr;
        height: auto;
        max-height: 70%;
        display: none;
        & #find {
            width: 1fr;
        }
        &.visible {
            display: block;
        }
        Input {
            width: 1fr;
        }
        Input#find-regex, Input#find-fields {
            display: none;
        }
        Input#find-text {
            display: block;
        }
        &.-find-regex {
            Input#find-regex {
                display: block;
            }
            Input#find-text {
                display: none;
            }
        }
        &.-find-fields {
            Input#find-fields {
                display: block;
            }
            Input#find-text {
                display: none;
            }
        }
    }    
    """
    BINDINGS = [
        Binding("escape", "dismiss_find", "Dismiss", key_display="esc", show=False),
        Binding("down,j", "pointer_down", "Next", key_display="↓"),
        Binding("up,k", "pointer_up", "Previous", key_display="↑"),
        Binding("j", "pointer_down", "Next", key_display="↓", show=False),
        Binding("k", "pointer_up", "Previous", key_display="↑", show=False),
        # priority: Input binds ctrl+e to "cursor to end"
        Binding("ctrl+e", "toggle_fields", "Fields", key_display="^e", priority=True),
    ]
    DEFAULT_CLASSES = "float"
    BORDER_TITLE = "Find"

    @dataclass
    class Update(Message):
        find: str
        regex: bool
        case_sensitive: bool
        fields: bool

    class Dismiss(Message):
        pass

    @dataclass
    class MovePointer(Message):
        direction: int = 1

    class SelectLine(Message):
        pass

    def __init__(
        self, suggester: Suggester, field_suggester: Suggester | None = None
    ) -> None:
        self.suggester = suggester
        self.field_suggester = field_suggester
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Input(
            placeholder="Regex",
            id="find-regex",
            suggester=self.suggester,
            validators=[Regex()],
        )
        yield Input(
            placeholder="Find",
            id="find-text",
            suggester=self.suggester,
        )
        yield Input(
            placeholder="Fields, e.g. level=ERROR gitlab_project_id=211",
            id="find-fields",
            suggester=self.field_suggester,
            validators=[FieldQueryValidator()],
        )
        yield Checkbox("Case sensitive", id="case-sensitive")
        yield Checkbox("Regex", id="regex")
        yield Checkbox("Fields", id="fields")

    @property
    def mode(self) -> str:
        if self.has_class("-find-fields"):
            return "fields"
        if self.has_class("-find-regex"):
            return "regex"
        return "text"

    def _input(self) -> Input:
        return self.query_one(f"#find-{self.mode}", Input)

    def focus_input(self) -> None:
        self._input().focus()

    def get_value(self) -> str:
        return self._input().value

    @on(Checkbox.Changed, "#regex")
    @on(Checkbox.Changed, "#fields")
    def on_checkbox_changed_mode(self, event: Checkbox.Changed) -> None:
        event.stop()
        value = self.get_value()
        if event.value:
            other = "#fields" if event.control.id == "regex" else "#regex"
            self.query_one(other, Checkbox).value = False
        self.set_class(self.query_one("#regex", Checkbox).value, "-find-regex")
        self.set_class(self.query_one("#fields", Checkbox).value, "-find-fields")
        typing = isinstance(self.app.focused, Input)
        self._input().value = value
        if typing:
            self.focus_input()
        self.post_update()

    @on(Input.Changed)
    @on(Checkbox.Changed, "#case-sensitive")
    def input_change(self, event: Input.Changed | Checkbox.Changed) -> None:
        event.stop()
        self.post_update()

    @on(Input.Submitted)
    def input_submitted(self, event: Input.Changed) -> None:
        event.stop()
        self.post_message(self.SelectLine())

    def post_update(self) -> None:
        update = FindDialog.Update(
            find=self.get_value(),
            regex=self.query_one("#regex", Checkbox).value,
            case_sensitive=self.query_one("#case-sensitive", Checkbox).value,
            fields=self.query_one("#fields", Checkbox).value,
        )
        self.post_message(update)

    def allow_focus_children(self) -> bool:
        return self.has_class("visible")

    def action_toggle_fields(self) -> None:
        fields = self.query_one("#fields", Checkbox)
        fields.value = not fields.value

    def action_dismiss_find(self) -> None:
        self.post_message(FindDialog.Dismiss())

    def action_pointer_down(self) -> None:
        self.post_message(self.MovePointer(direction=+1))

    def action_pointer_up(self) -> None:
        self.post_message(self.MovePointer(direction=-1))
