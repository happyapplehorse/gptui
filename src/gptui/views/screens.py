import logging
import os

from textual import events
from textual.app import ComposeResult
from textual.containers import Grid
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Input, MarkdownViewer

from .custom_tree import MyDirectoryTree
from ..utils.my_text import MyText as Text


gptui_logger = logging.getLogger("gptui_logger")


class CheckDialog(ModalScreen[bool]):
    """Check an action."""

    CSS = """
    CheckDialog {
        align: center middle;
    }
    CheckDialog > #dialog {
        grid-size: 2;
        grid-gutter: 1 2;
        grid-rows: 1fr 3;
        padding: 0 1;
        width: 60;
        height: 11;
        border: thick $background 80%;
        background: $surface;
    }
    CheckDialog #prompt {
        column-span: 2;
        height: 1fr;
        width: 1fr;
        content-align: center middle;
    }
    CheckDialog Button {
        width: 100%;
    }
    """

    def __init__(self, prompt: str | Text = "Are you sure?", yes_label: str = "Yse", no_label: str = "No", *args, **kwargs):
        self.prompt = prompt
        self.yes_label = yes_label
        self.no_label = no_label
        super().__init__(*args, **kwargs)

    def compose(self) -> ComposeResult:
        yield Grid(
            Label(self.prompt, id="prompt"),
            Button(self.yes_label, id="yes"),
            Button(self.no_label, id="no"),
            id="dialog",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "yes":
            self.dismiss(True)
        elif event.button.id == "no":
            self.dismiss(False)


class InputDialog(ModalScreen[tuple[bool, str]]):
    """Ask whether to close the conversation."""

    CSS = """
    InputDialog {
        align: center middle;
    }
    InputDialog > #dialog {
        grid-size: 2;
        grid-gutter: 1 2;
        grid-rows: 1fr 2fr 3;
        padding: 0 1;
        width: 60;
        height: 11;
        border: thick $background 80%;
        background: $surface;
    }
    InputDialog #input {
        column-span: 2;
        height: 1fr;
        width: 1fr;
    }
    InputDialog #prompt {
        column-span: 2;
        height: 1fr;
        width: 1fr;
        content-align: center middle;
    }
    InputDialog Button{
        width: 100%;
    }
    """

    def __init__(self, prompt: str | Text = "Input:", placeholder: str = "", default_input: str | None = None, ok_label: str = "OK", cancel_label: str = "Cancel", *args, **kwargs):
        self.prompt = prompt
        self.placeholder = placeholder
        self.default_input = default_input
        self.ok_label = ok_label
        self.cancel_label = cancel_label
        super().__init__(*args, **kwargs)

    def compose(self) -> ComposeResult:
        self.input = Input(placeholder=self.placeholder, id="input")
        yield Grid(
            Label(self.prompt, id="prompt"),
            self.input,
            Button(self.ok_label, id="ok"),
            Button(self.cancel_label, id="cancel"),
            id="dialog",
        )
    
    def on_mount(self):
        if self.default_input:
            self.input.value = self.default_input

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ok":
            self.dismiss((True, self.input.value))
        elif event.button.id == "cancel":
            self.dismiss((False, self.input.value))


class SelectPathDialog(ModalScreen[tuple[bool, str]]):
    """Ask whether to close the conversation."""

    CSS = """
    SelectPathDialog {
        align: center middle;
    }
    SelectPathDialog > #dialog {
        grid-size: 2;
        grid-gutter: 1 2;
        grid-rows: 1 1fr 2fr 3;
        padding: 0 1;
        width: 60;
        height: 20;
        border: thick $background 80%;
        background: $surface;
    }
    SelectPathDialog #input {
        column-span: 2;
        height: 1;
        width: 1fr;
    }
    SelectPathDialog #select_path_directory_tree {
        column-span: 2;
        height: 1fr;
        width: 1fr;
    }
    SelectPathDialog #prompt {
        column-span: 2;
        height: 1;
        width: 1fr;
        content-align: center middle;
    }
    SelectPathDialog Button{
        width: 100%;
    }
    """

    def __init__(
        self,
        root_directory_path: str,
        prompt: str | Text = "Input:",
        placeholder: str = "",
        ok_label: str = "OK",
        cancel_label: str = "Cancel",
        *args,
        **kwargs
        ):
        self.root_directory_path = root_directory_path
        self.prompt = prompt
        self.placeholder = placeholder
        self.ok_label = ok_label
        self.cancel_label = cancel_label
        super().__init__(*args, **kwargs)

    def compose(self) -> ComposeResult:
        self.input = Input(placeholder=self.placeholder, id="input")
        yield Grid(
            Label(self.prompt, id="prompt"),
            self.input,
            MyDirectoryTree(self.root_directory_path, self.root_directory_path, id="select_path_directory_tree"),
            Button(self.ok_label, id="ok"),
            Button(self.cancel_label, id="cancel"),
            id="dialog",
        )

    def on_tree_node_highlighted(self, event) -> None:
        selected_path = event.node.data.path
        if selected_path.is_file():
            self.input.value = str(selected_path.parent) + os.sep
        if selected_path.is_dir():
            self.input.value = str(selected_path) + os.sep
    
    async def on_input_submitted(self, message) -> None:
        self.dismiss((True, message.value))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ok":
            self.dismiss((True, self.input.value))
        elif event.button.id == "cancel":
            self.dismiss((False, self.input.value))


class MarkdownPreview(ModalScreen):
    
    CSS = """
    MarkdownPreview {
        align: center middle;
    }
    MarkdownPreview MarkdownViewer {
        width: 50%;
        height: 50%;
        border: ascii $accent;
    }
    """

    BINDINGS = [
        ("space", "quit", "Quit"),
    ]

    def __init__(self, markdown: str | None = None, previewer_title: str | None = None, *args, **kwargs):
        self.markdown = markdown
        self.previewer_title = previewer_title
        super().__init__(*args, **kwargs)

    def on_mount(self) -> None:
        previewer = self.query_one(MarkdownViewer)
        if self.previewer_title is not None:
            previewer.border_title = self.previewer_title
        previewer.border_subtitle = "Press 'space' to close this previewer"
    
    def compose(self) -> ComposeResult:
        yield MarkdownViewer(self.markdown, show_table_of_contents=False)

    def action_quit(self) -> None:
        self.app.pop_screen()


class HotKey(ModalScreen[str]):

    CSS = """
    HotKey {
        align: center bottom;
    }
    HotKey Label {
        width: 80;
        height: 12;
        text-align: center;
        border: ascii $accent;
    }
    """

    BINDINGS = [
        ("escape,ctrl+underscore", "quit", "Quit"),
    ]

    def __init__(self, display_content: str | Text, *args, **kwargs):
        self.display_content = display_content
        super().__init__(*args, **kwargs)

    def compose(self) -> ComposeResult:
        yield Label(self.display_content)

    def action_quit(self) -> None:
        self.app.pop_screen()

    def on_key(self, event: events.Key) -> None:
        self.dismiss(event.key)
