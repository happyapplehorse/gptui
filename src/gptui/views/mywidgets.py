from __future__ import annotations
import asyncio
import inspect
import logging
import os
import textwrap
from typing import NamedTuple, Callable, Awaitable, Coroutine, TypeVar, Generic

from rich.console import RenderResult, Console
from rich.style import Style
from rich.text import TextType
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, Grid
from textual.css.query import NoMatches
from textual.geometry import Size, Offset
from textual.message import Message
from textual.message_pump import _MessagePumpMeta
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import (
    Button,
    DirectoryTree,
    Input,
    Label,
    Markdown,
    RichLog,
    Switch,
    Static,
)

from .screens import SelectPathDialog, MarkdownPreview
from .theme import ThemeColor
from .theme import theme_color as tc
from ..controllers.tube_files_control import TubeFiles
from ..models.doc import Doc
from ..utils.file_icon import file_icon
from ..utils.line_count import my_line_count
from ..utils.my_text import MyText as Text
from ..utils.my_text import MyLines as Lines


gptui_logger = logging.getLogger("gptui_logger")

CheckBoxPointer = TypeVar("CheckBoxPointer")
"""The type of the pointer for a given instance of a [CheckBox]"""

SliderPointer = TypeVar("SliderPointer")
"""The type of the pointer for a given instance of a [Slider]"""


class MyFillIn(Widget):
    """
    Fill area with characters.
    args:
        char: The characters to fill with.
        width: The width of filling area, int or percentage str (int%).
        height: The height of filling area, int or percentage str (int%).
            number refers to the absolute number of rows or columns, and the number% is relative to the container.
        x_start: drawing offsets.
        y_start: drawing offsets.
        color: str of color.
            example: #002CFF, grb(20,200,2)
    """
    def __init__(
        self,
        char: str,
        width: int | str = '100%',
        height: int | str = '100%',
        x_start: int | str = '0%',
        y_start: int | str = '0%',
        color: str | None = None,
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.width = width
        self.height = height
        self.char = char
        self.x_start = x_start
        self.y_start = y_start
        self.color = color

    def render(self) -> RenderResult:
        import math
        if isinstance(self.width, int):
            width = self.width
        elif isinstance(self.width, str) and self.width.endswith('%'):
            width = math.floor(self.content_size.width * float(self.width.strip('%')) / 100)
        else:
            raise TypeError(f"Expected a int or a percentage string, bug got{type(self.width).__name__} instead.")
        if isinstance(self.height, int):
            height = self.height
        elif isinstance(self.height, str) and self.height.endswith('%'):
            height = math.floor(self.content_size.height * float(self.height.strip('%')) / 100)
        else:
            raise TypeError(f"Expected a int or a percentage string, bug got{type(self.height).__name__} instead.")
        if isinstance(self.x_start, int):
            x_start = self.x_start
        elif isinstance(self.x_start, str) and self.x_start.endswith('%'):
            x_start = math.floor(self.content_size.width * float(self.x_start.strip('%')) / 100)
        else:
            raise TypeError(f"Expected a int or a percentage string, bug got{type(self.x_start).__name__} instead.")
        if isinstance(self.y_start, int):
            y_start = self.y_start
        elif isinstance(self.y_start, str) and self.y_start.endswith('%'):
            y_start = math.floor(self.content_size.width * float(self.y_start.strip('%')) / 100)
        else:
            raise TypeError(f"Expected a int or a percentage string, bug got{type(self.y_start).__name__} instead.")

        string = '\n' * y_start + (' ' * x_start + self.char * width + '\n') * height
        result = Text(string, style=Style(color=self.color))
        return result


class MyScroll(NamedTuple):
    x_start: float
    x_end: float
    y_start: float
    y_end: float
    def clamped(self):
        x_start, x_end, y_start, y_end = self
        return MyScroll(0 if x_start < 0 else x_end if x_start > x_end else x_start,
                        1 if x_end > 1 else x_start if x_start > x_end else x_end,
                        0 if y_start < 0 else y_end if y_start > y_end else y_start,
                        1 if y_end > 1 else y_start if y_start > y_end else y_end)


class MyScrollSupportMixin(Widget):

    class MyScrollChanged(Message):
        def __init__(self, my_scroll: MyScroll, id: str|None = None) -> None:
            self.my_scroll = my_scroll
            self.id = id
            super().__init__()

    class MyScrollOffsetChanged(Message):
        def __init__(self, my_scroll_offset: Offset, id: str|None = None) -> None:
            self.my_scroll_offset = my_scroll_offset
            self.id = id
            super().__init__()
    
    def init(self):
        self.mouse_move_start_point = False
        self.mouse_move_status = False
    
    my_scroll_offset = reactive(Offset(0,0))
    my_scroll = reactive(MyScroll(0,1,0,1))
    
    def set_scroll(self, x_start: float = 0, x_end: float = 1, y_start: float = 0, y_end: float = 1):
        self.my_scroll = MyScroll(x_start, x_end, y_start, y_end)
    def move_scroll(self, x: float = 0, y: float = 0):
        self.my_scroll = MyScroll(self.my_scroll.x_start + x, self.my_scroll.x_end + x, self.my_scroll.y_start + y, self.my_scroll.y_end + y)

    @property
    def my_scroll_display_size(self) -> Size: 
        return self.my_set_display_size() if callable(self.my_set_display_size) else self.my_set_display_size
    @property
    def my_scroll_virtual_size(self) -> Size:
        return self.my_set_virtual_size() if callable(self.my_set_virtual_size) else self.my_set_virtual_size

    def _my_compute_my_scroll(self) -> MyScroll:
        scroll_x_start = self.my_scroll_offset.x / self.my_scroll_virtual_size.width
        scroll_x_end = (self.my_scroll_offset.x + self.my_scroll_display_size.width) / self.my_scroll_virtual_size.width
        scroll_y_start = self.my_scroll_offset.y / self.my_scroll_virtual_size.height
        scroll_y_end = (self.my_scroll_offset.y + self.my_scroll_display_size.height) / self.my_scroll_virtual_size.height
        return MyScroll(scroll_x_start, scroll_x_end, scroll_y_start, scroll_y_end).clamped()

    def watch_my_scroll_offset(self, new_value) -> None:
        if self.content_size.width != 0:
            self.my_scroll = self._my_compute_my_scroll()
        self.post_message(self.MyScrollOffsetChanged(self.my_scroll_offset, self.id))
    def watch_my_scroll(self, my_scroll) -> None:
        self.post_message(self.MyScrollChanged(self.my_scroll, self.id))

    def my_scroll_content_to_render(self, content_wrap: Lines, y: int = 0, h: int = 0, x: int = 0, w: int = 0) -> Text:
        result = Text()
        line_nums = len(content_wrap)
        start_line = min(y, line_nums)
        end_line = min(y+h, line_nums)
        for line in content_wrap[start_line:end_line]:
            result.append_text(line)
            result.append_text(Text('\n'))
        return result

# 鼠标拖动的滚动支持
#    def on_mouse_move(self, event: events.MouseMove) -> None:
#        if self.mouse_move_start_point and 0 <= event.x <= self.my_scroll_display_size.width and 0 <= event.y <= self.my_scroll_display_size.height:
#            if not self.mouse_move_status:
#                delta_x = 0
#                delta_y = 0
#            else:
#                delta_x = event.delta_x
#                delta_y = event.delta_y
#            self.mouse_move_status = True
#            if self.my_scroll_virtual_size.width > self.my_scroll_display_size.width:
#                self.my_scroll_offset = Offset(self.my_scroll_offset.x - delta_x, self.my_scroll_offset.y)
#                if self.my_scroll_offset.x < 0:
#                    self.my_scroll_offset = Offset(0, self.my_scroll_offset.y)
#                if self.my_scroll_offset.x > self.my_scroll_virtual_size.width - self.my_scroll_display_size.width:
#                    self.my_scroll_offset = Offset(self.my_scroll_virtual_size.width - self.my_scroll_display_size.width, self.my_scroll_offset.y)
#            else:
#                self.my_scroll_offset = Offset(0, self.my_scroll_offset.y)
#            if self.my_scroll_virtual_size.height > self.my_scroll_display_size.height:
#                self.my_scroll_offset = Offset(self.my_scroll_offset.x, self.my_scroll_offset.y - delta_y)
#                if self.my_scroll_offset.y < 0:
#                    self.my_scroll_offset = Offset(self.my_scroll_offset.x, 0)
#                if self.my_scroll_offset.y > self.my_scroll_virtual_size.height - self.my_scroll_display_size.height:
#                    self.my_scroll_offset = Offset(self.my_scroll_offset.x, self.my_scroll_virtual_size.height - self.my_scroll_display_size.height)
#            else:
#                self.my_scroll_offset = Offset(self.my_scroll_offset.x, 0)
#    
#    def on_mouse_up(self, event) -> None:
#        self.mouse_move_status = False
#        self.mouse_move_start_point = False
#    def on_mouse_down(self, event) -> None:
#        if 0 <= event.x <= self.my_scroll_display_size.width and 0 <= event.y <= self.my_scroll_display_size.height:
#            self.mouse_move_start_point = True

    def on_mouse_scroll_up(self, event) -> None:
        if self.my_scroll_virtual_size.height > self.my_scroll_display_size.height:
            self.my_scroll_offset = Offset(self.my_scroll_offset.x, self.my_scroll_offset.y - 1)
            if self.my_scroll_offset.y < 0:
                self.my_scroll_offset = Offset(self.my_scroll_offset.x, 0)
            if self.my_scroll_offset.y > self.my_scroll_virtual_size.height - self.my_scroll_display_size.height:
                self.my_scroll_offset = Offset(self.my_scroll_offset.x, self.my_scroll_virtual_size.height - self.my_scroll_display_size.height)
        else:
            self.my_scroll_offset = Offset(self.my_scroll_offset.x, 0)
    def on_mouse_scroll_down(self, event) -> None:
        if self.my_scroll_virtual_size.height > self.my_scroll_display_size.height:
            self.my_scroll_offset = Offset(self.my_scroll_offset.x, self.my_scroll_offset.y + 1)
            if self.my_scroll_offset.y < 0:
                self.my_scroll_offset = Offset(self.my_scroll_offset.x, 0)
            if self.my_scroll_offset.y > self.my_scroll_virtual_size.height - self.my_scroll_display_size.height:
                self.my_scroll_offset = Offset(self.my_scroll_offset.x, self.my_scroll_virtual_size.height - self.my_scroll_display_size.height)
        else:
            self.my_scroll_offset = Offset(self.my_scroll_offset.x, 0)


class MyMultiInput(Input, MyScrollSupportMixin):
    """
    use "on_input_submitted" method to handle the submitting event.
    """
    # TODO: uncompleted
    Input.BINDINGS = [
        Binding("left", "cursor_left", "cursor left", show=False),
        Binding("ctrl+left", "cursor_left_word", "cursor left word", show=False),
        Binding("right", "cursor_right", "cursor right", show=False),
        Binding("ctrl+right", "cursor_right_word", "cursor right word", show=False),
        Binding("backspace", "delete_left", "delete left", show=False),
        Binding("home,ctrl+a", "home", "home", show=False),
        Binding("end,ctrl+e", "end", "end", show=False),
        Binding("delete,ctrl+d", "delete_right", "delete right", show=False),
        Binding("enter", "submit", "submit", show=False),
        Binding(
            "ctrl+w", "delete_left_word", "delete left to start of word", show=False
        ),
        Binding("ctrl+u", "delete_left_all", "delete all to the left", show=False),
        Binding(
            "ctrl+f", "delete_right_word", "delete right to start of word", show=False
        ),
        Binding("ctrl+k", "delete_right_all", "delete all to the right", show=False),
        Binding("up", "cursor_up", "cursor up"),
        Binding("down", "cursor_down", "cursor down"),
        Binding("shift+left", "change_line", "change line"),
    ]   

#    def __init__(self,*args,**kwargs):
#        Input.__init__(self,*args,**kwargs)
#        MyScrollSupportMixin.__init__(self)
    def on_mount(self):
        MyScrollSupportMixin.init(self)
        #self.capture_mouse()
        self.my_set_display_size = self.display_size_send
        self.my_set_virtual_size = self.virtual_size_send

    def virtual_size_send(self):
        width = self.content_size.width
        height = my_line_count(self._value, width)
        return Size(width, height)
    def display_size_send(self):
        return self.content_size

    def render(self) -> RenderResult:
        if not self.value:
            placeholder = Text(self.placeholder, justify="left")
            placeholder.stylize(self.get_component_rich_style("input--placeholder"))
            if self.has_focus:
                cursor_style = self.get_component_rich_style("input--cursor")
                if self._cursor_visible:
                    # If the placeholder is empty, there's no characters to stylise
                    # to make the cursor flash, so use a single space character
                    if len(placeholder) == 0:
                        placeholder = Text(" ")
                    placeholder.stylize(cursor_style, 0, 1)
            return placeholder
        return self._my_render_content(self, self._cursor_visible)

    def _my_render_content(self, input, cursor_visible) -> RenderResult:
        content = input._value
        scroll_x, scroll_y = input.my_scroll_offset
        if input._cursor_at_end:
            content.pad_right(1)
        cursor_style = input.get_component_rich_style("input--cursor")
        if cursor_visible and input.has_focus:
            cursor = input.cursor_position
            content.stylize(cursor_style, cursor, cursor+1)
        width = input.content_size.width
        height = input.content_size.height
        length = content.cell_len
        content_wrap = content.wrap(console=Console(), width=self.content_size.width, overflow="fold", no_wrap=False)
        return self.my_scroll_content_to_render(content_wrap, y=scroll_y, h=height)

    def action_cursor_up(self) -> None:
        self.cursor_position -= self.content_size.width
    def action_cursor_down(self) -> None:
        self.cursor_position += self.content_size.width
    def action_change_line(self) -> None:
        self.value = self.value + "\n"
        self.cursor_position += self.content_size.width - self.cursor_position % self.content_size.width
    def action_submit(self):
        self.post_message(self.Submitted(self, self.value))
        self.value = ""


class MyChatWindow(MyScrollSupportMixin):
    """
    supplied two write content method:
    1. update, write, right_crop
    2. update_lines, write_lines, right_pop_lines
    methods with line is recomended
    Important: always use only one serial methods, mix use will cause error
    """
    def on_mount(self):
        MyScrollSupportMixin.init(self)
        #self.capture_mouse()
        self.my_set_display_size = self.display_size_send
        self.my_set_virtual_size = self.virtual_size_send
        self.my_content = Text()
        self.my_content_wrap = Lines()
        self.refresh_content_wrap_request = False
        self.right_crop_request = 0
        self.right_crop_request = 0

    def virtual_size_send(self):
        width = self.content_size.width
        height = len(self.my_content_wrap)
        return Size(width, height)
    
    def display_size_send(self):
        return self.content_size

    def clear(self, refresh: bool = True):
        self.my_content = Text()
        self.my_content_wrap = Lines()
        self.right_crop_request = 0
        self.right_pop_lines_request = 0
        self.refresh_content_wrap_request = False
        if refresh:
            self.refresh()

    def update(self, content: Text, scroll_to_end: bool = True) -> None:
        self.my_content = content
        self.my_content_wrap = self.my_content.wrap(console=Console(), width=self.content_size.width, overflow="fold", no_wrap=False)
        if scroll_to_end:
            self.scroll_to_end()
        self.refresh()
        self.right_crop_request = 0
        self.refresh_content_wrap_request = False
    
    def write(self, content: Text, scroll_to_end: bool = True) -> None:
        console = Console()
        width = self.content_size.width
        if self.right_crop_request:
            self.my_content.right_crop(self.right_crop_request) # right_crop(0) will crop all characters, so should be skipped
            self.right_crop_request = 0
            self.my_content.append_text(content)
            self.my_content_wrap = self.my_content.wrap(console=console, width=width, overflow="fold", no_wrap=False)
            self.refresh_content_wrap_request = False
        else:
            if self.refresh_content_wrap_request is True:
                self.refresh_content_wrap()
                self.refresh_content_wrap_request = False
            self.my_content.append_text(content)
            if self.my_content_wrap:
                last_line = self.my_content_wrap.pop()
            else:
                last_line = Text()
            last_line.append_text(content)
            last_line_after = last_line.wrap(console=console, width=width, overflow="fold", no_wrap=False)
            self.my_content_wrap.extend(last_line_after)
        if scroll_to_end:
            self.scroll_to_end()
        self.refresh()

    def scroll_to_end(self, refresh: bool = False):
        if self.refresh_content_wrap_request is True:
            self.refresh_content_wrap()
            self.refresh_content_wrap_request = False
        offset_y = self.my_scroll_virtual_size.height - self.my_scroll_display_size.height
        self.my_scroll_offset = Offset(self.my_scroll_offset.x, offset_y if offset_y > 0 else 0)
        if refresh is True:
            self.refresh()
    
    def right_crop(self, amount: int, refresh: bool = True, scroll_to_end: bool = False) -> None:
        if refresh:
            amount += self.right_crop_request
            if amount:
                self.my_content.right_crop(amount) # right_crop(0) will crop all characters, so should be skipped
                self.my_content_wrap = self.my_content.wrap(console=Console(), width=self.content_size.width, overflow="fold", no_wrap=False)
            if scroll_to_end:
                self.scroll_to_end()
            self.refresh()
            self.right_crop_request = 0
            self.refresh_content_wrap_request = False
        else:
            self.right_crop_request += amount

    def write_content_without_display(self, content: Text):
        self.my_content.append_text(content)
        self.refresh_content_wrap_request = True

    def refresh_content_wrap_request_execute(self):
        if self.refresh_content_wrap_request is True:
            self.refresh_content_wrap()
            self.refresh_content_wrap_request = False

    def refresh_content_wrap(self):
        if self.my_content:
            self.my_content_wrap = self.my_content.wrap(console=Console(), width=self.content_size.width, overflow="fold", no_wrap=False)
        else:
            self.my_content_wrap = Lines()

    def update_lines(self, content_lines: Lines, scroll_to_end: bool = True) -> None:
        self.my_content_wrap = content_lines
        if scroll_to_end:
            self.scroll_to_end()
        self.refresh()
        self.right_pop_lines_request = 0

    def write_lines(self, content_lines: Lines, scroll_to_end: bool = True) -> None:
        if self.right_pop_lines_request:
            num = min(self.right_pop_lines_request, len(self.my_content_wrap))
            for _ in range(num):
                self.my_content_wrap.pop()
            self.right_pop_lines_request = 0
        self.my_content_wrap.extend(content_lines)
        if scroll_to_end:
            self.scroll_to_end()
        self.refresh()

    def right_pop_lines(self, amount: int, refresh: bool = True, scroll_to_end: bool = False) -> list[Text]:
        if refresh:
            amount += self.right_pop_lines_request
            out = []
            amount = min(amount, len(self.my_content_wrap))
            for _ in range(amount):
                out.append(self.my_content_wrap.pop())
            if scroll_to_end:
                self.scroll_to_end()
            self.refresh()
            return out.reverse()
        else:
            self.right_pop_lines_request += amount
            return []

    @property
    def my_render_content(self) -> Text:
        scroll_x, scroll_y = self.my_scroll_offset
        return self.my_scroll_content_to_render(self.my_content_wrap, y = scroll_y, h = self.my_scroll_display_size.height)

    def render(self) -> RenderResult:
        result = self.my_render_content
        return result

    class Resize(Message):
        def __init__(self, event):
            self.event = event
            super().__init__()

    def on_resize(self, event) -> None:
        self.post_message(self.Resize(event))


class _InputDialog(Widget):
    """This is a awaitable input dialog. May be useful."""
    # Not used yet, switched to using InputDialog by Screen. Kept as future reference.
    """
    It should be run in a worker!
    """
    
    DEFAULT_CSS = """
    _InputDialog{
        width: 50;
        height: 12;
        border: round;
    }
    Input{
        height: 1;
    }
    Label{
        border: none;
    }
    Button{
        width: 12;
        min-width: 6;
        min-height: 1;
    }
    """
    def __init__(self, prompt: str, *args, **kwargs) -> None:
        self.prompt = prompt
        self.status = False
        self.value: str|None = ''
        super().__init__(*args, **kwargs)

    def on_mount(self) -> None:
        self.border_title = "Input Dialog"
        self.query_one("#label").styles.border = None
        
    def compose(self) -> ComposeResult:
        yield Label(self.prompt, id = "label")
        yield Input()
        with Horizontal():
            yield Button("OK")
            yield Button("Default")
            yield Button("Cancel")

    def on_button_pressed(self, event) -> None:
        if event.button.label == "OK":
            self.value = self.query_one(Input).value
        elif event.button.label == "Cancel":
            self.value = None
        else:
            self.value = self.query_one(Input).value
        self.status = True

    @classmethod
    async def my_input_dialog(cls, app, prompt: str) -> str|None:
        dialog_instance = _MyInputDialog(prompt, classes = "top_layer")
        await app.mount(dialog_instance)
        while not dialog_instance.status:
            await asyncio.sleep(0.1)
        result = dialog_instance.value
        dialog_instance.remove()
        return result


class Tube(Widget):
    DEFAULT_CSS = """
    Tube Horizontal{
        height: 1;
    }
    Tube Button{
        border: none;
        width: 10;
        min-width: 5;
        height: 1;
        min-height: 1;
        padding: 0;
        margin: 0;
    }
    #up_control {
        height: 1;
        grid-size: 3 1;
        grid-columns: 10 1fr 4;
    }
    Tube GridContentUp {
        background: rgb(30, 35, 50);
    }
    Tube GridContentDown {
        background: rgb(30, 35, 50);
    }
    #up_tube{
        height: 1fr;
    }
    #down_tube{
        height: 1fr;
    }
    """

    def __init__(self, app, **kwargs):
        self.myapp = app
        super().__init__(**kwargs)
        self.up_tube_list = []
        self.down_tube_list = []
        self.export_content = None

    def compose(self) -> ComposeResult:
        with Vertical():
            with Grid(id="up_control"):
                yield Button("|Import|", id="up_import")
                yield Button("|Clear|", id="up_clear")
                yield Switch(value=False, id="send_switch", classes="min_switch")
            yield GridContentMake(name="GridContentUp", id="up_tube", column_num=4, grid_rows="5")
            with Horizontal():
                yield Button("|Export|", id="down_export")
                yield Button("|Delete|", id="down_delete")
                yield Button("|Clear|", id ="down_clear")
            yield GridContentMake(name="GridContentDown", id="down_tube", column_num=4, grid_rows="5")

    def on_mount(self):
        export_button = self.query_one("#down_export")
        delete_button = self.query_one("#down_delete")
        export_button.can_focus = False
        delete_button.can_focus = False

    def add_document_to_up_tube(self, document: Doc) -> None:
        self.up_tube_list.append(document)
        document_name = document.name
        file_type = document.ext
        file_description = document_name + file_type
        up_tube = self.query_one("#up_tube")
        up_tube.add_children(
            FileIcon(
                pointer=document,
                file_type=file_type,
                file_label=document_name,
                file_description=file_description,
                previewer=self.myapp,
            )
        )

    def add_document_to_down_tube(self, document: Doc) -> None:
        self.down_tube_list.append(document)
        doc_ext = document.ext
        doc_name = document.name
        down_tube = self.query_one("#down_tube")
        down_tube.add_children(
            FileIcon(
                pointer=document,
                file_type=doc_ext,
                file_label=doc_name,
                file_description = doc_name + doc_ext,
                previewer=self.myapp,
            )
        )
    
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "up_import":
            self.myapp.main_screen.query_one("#middle_switch").change_to_pointer("directory_tree")
        if button_id == "up_clear":
            self.query_one("#up_tube").clear()
            self.up_tube_list = []
        if button_id == "down_export":
            try:
                focused_file = self.query("#down_tube > FileIcon:focus").first()
            except NoMatches:
                self.myapp.main_screen.query_one("#status_region").update(Text("No file is selected.", tc("yellow") or "yellow"))
            except Exception as e:
                self.myapp.main_screen.query_one("#status_region").update(Text(f"{e}", tc("yellow") or "yellow"))
            else:
                self.export_content = focused_file.pointer.content
                self.myapp.push_screen(
                    SelectPathDialog(
                        root_directory_path=self.myapp.config["directory_tree_path"],
                        prompt="Determine the file path and name (including extension):",
                        placeholder="filename"
                    ),
                    self._save_file,
                )
        if button_id == "down_clear":
            self.query_one("#down_tube").clear()
            self.down_tube_list = []
        if button_id == "down_delete":
            try:
                focused_file = self.query("#down_tube > FileIcon:focus").first()
            except NoMatches:
                self.myapp.main_screen.query_one("#status_region").update(Text("No file is selected.", tc("yellow") or "yellow"))
            except Exception as e:
                self.myapp.main_screen.query_one("#status_region").update(Text(f"{e}", tc("yellow") or "yellow"))
            else:
                self.query_one("#down_tube").remove_child(focused_file)
                self.down_tube_list.remove(focused_file.pointer)

    async def _save_file(self, selected_path: tuple[bool, str]) -> None:
        status, path = selected_path
        if status is False:
            return
        status_region = self.myapp.main_screen.query_one("#status_region")
        
        # Check whether it includes a path name.
        dirname, filename = os.path.split(path)
        if not dirname:
            path = os.path.join(self.myapp.config["workpath"], filename)

        if os.path.isfile(path):
            status_region.update(Text("File is not exported beacause file name have existed!", tc("red") or "red"))
            return
        if not self.export_content:
            status_region.update(Text("File is empty! Not exported.", tc("yellow") or "yellow"))
            return
        tf = TubeFiles(status_region)
        await tf.write_file_async(file_path=path, file_content=self.export_content)

    def get_upload_files(self) -> list[Doc]:
        return self.up_tube_list

    def refresh_display(self) -> None:
        up_tube_list = self.up_tube_list.copy()
        down_tube_list = self.down_tube_list.copy()
        self.query_one("#up_tube").clear()
        self.query_one("#down_tube").clear()
        self.up_tube_list = []
        self.down_tube_list = []
        for doc in up_tube_list:
            self.add_document_to_up_tube(doc)
        for doc in down_tube_list:
            self.add_document_to_down_tube(doc)


class MultiGridContent(Widget):
    DEFAULT_CSS = """
    MultiGridContent > * {
        height: 8;
        border: none;
        background: rgb(30, 35, 50);
    }
    MultiGridContent MyFillIn {
        height: 1;
        color: rgb(100,100,100);
        background: rgb(30, 35, 50);
        opacity: 0.5;
    }
    MultiGridContent {
        background: rgb(30, 35, 50);
    }
    """
    
    def __init__(self, grid_list: list, **kwargs):
        self.init_grid_list = grid_list
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        yield self.init_grid_list[0]
        for grid_content in self.init_grid_list[1:]:
            yield MyFillIn(char="\u2500", width="80%", x_start="10%")
            yield grid_content

    def add_grid_content(
        self,
        *grid_contents,
        before: int | str | Widget | None = None,
        after: int | str | Widget | None = None
    ) -> None:
        self.mount(*grid_contents, before=before, after=after)

    def add_horizontal_line(
        self,
        char: str,
        before: int | str | Widget | None = None,
        after: int | str | Widget | None = None,
    ) -> None:
        self.mount(MyFillIn(char), before=before, after=after)
    
    @property
    def grid_content_list(self) -> list:
        children = self.query("MultiGridContent > GridContentBase")
        return list(children)

    @property
    def horizontal_line_list(self) -> list:
        children = self.query("MultiGridContent > MyFillIn")
        return list(children)
    
    @property
    def children_list(self) -> list:
        children = self.query("MultiGridContent > *")
        return list(children)

    def remove_grid_content(self, child: int | Widget) -> None:
        if isinstance(child, int):
            try:
                grid_content = self.grid_content_list[child]
                grid_content.remove()
                position = self.children.index(grid_content)
                if position < len(self.children_list) - 1:
                    if isinstance(self.children_list[position + 1], MyFillIn):
                        self.children_list[position + 1].remove()
            except IndexError as e:
                gptui_logger.error(e)
        else:
            child.remove()
            position = self.children_list.index(child)
            if position < len(self.children_list) - 1:
                if isinstance(self.children_list[position + 1], MyFillIn):
                    self.children_list[position + 1].remove()
    
    def remove_horizontal_line(self, line: int | MyFillIn) -> None:
        if isinstance(line, int):
            try:
                my_fill_in = self.horizontal_line_list[line]
                my_fill_in.remove()
            except IndexError as e:
                gptui_logger.error(e)
        else:
            line.remove()

    def clear(self):
        self.remove_children()


class GridContentMeta(_MessagePumpMeta):
    def __new__(mcs, name, bases, attrs):

        def __init__(
            self, 
            column_num: int, 
            row_num: int | None = None, 
            grid_columns: str = "1fr", 
            grid_rows: str = "2", 
            **kwargs
        ):
            self.column_num = column_num
            self.row_num = row_num
            super(self.__class__, self).__init__(**kwargs)
            # set the grid layout
            self.__class__.DEFAULT_CSS += f"{name} {{layout: grid; grid-size:{column_num} {row_num if row_num else ''}; grid-columns: {grid_columns}; grid-rows: {grid_rows}; grid-gutter: 1;}}"
        
        def add_children(
            self,
            *children,
            before: int | str | Widget | None = None,
            after: int | str | Widget | None = None
        ) -> None:
            self.mount(*children, before=before, after=after)

        def update_children(self, *args, **kwargs) -> None:
            self.clear()
            self.add_children(*args, **kwargs)
        
        def remove_child(self, child: str | Widget) -> None:
            if isinstance(child, str):
                try:
                    self.query_one(child).remove()
                except NoMatches as e:
                    gptui_logger.error(e)
            else:
                child.remove()
        
        def remove_child_last(self) -> None:
            try:
                children = self.query("GridContentBase > *")
                children.last().remove()
            except NoMatches:
                return
        
        def remove_child_first(self):
            try:
                children = self.query("GridContentBase > *")
                children.first().remove()
            except NoMatches:
                return
        
        def clear(self):
            self.remove_children()

        def change_child_order(
            self,
            child,
            before: int | Widget | None = None,
            after: int | Widget | None = None
        ) -> None:
            self.move_child(child, before=before, after=after)
        
        attrs["DEFAULT_CSS"] = f"""
        .box {{
            height: 100%;
            border: solid {tc("green") or "green"};
        }}
        """
        attrs["__init__"] = __init__
        attrs["add_children"] = add_children
        attrs["update_children"] = update_children
        attrs["remove_child"] = remove_child
        attrs["remove_child_last"] = remove_child_last
        attrs["remove_child_first"] = remove_child_first
        attrs["clear"] = clear
        attrs["change_child_order"] = change_child_order

        return type.__new__(mcs, name, bases, attrs)


class GridContentBase(Widget):
    """Base class for GridContent and GridContentMake

    Each GridContentMake must be assigned a unique class name upon instantiation;
    therefore, the name of each GridContentMake is actually distinct and uncertain.
    This base class can be used to determine if a class is a GridContentMake or GridContent.
    """

class GridContentMake:
    """
    A container that put its contents in a grid.
    """
    def __new__(
        cls,
        name: str,
        column_num: int, 
        row_num: int | None = None, 
        grid_columns: str = "1fr", 
        grid_rows: str = "2", 
        **kwargs
    ):
        return GridContentMeta(name, (GridContentBase,), {})(column_num=column_num, row_num=row_num, grid_columns=grid_columns, grid_rows=grid_rows, **kwargs)


class GridContent(GridContentBase):

    DEFAULT_CSS = """
    GridContent {
        layout: grid;
        grid-size: 4;
        grid-columns: 1fr;
        grid-rows: 2;
        grid-gutter: 1;
    }
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def add_children(
        self,
        *children,
        before: int | str | Widget | None = None,
        after: int | str | Widget | None = None
    ) -> None:
        self.mount(*children, before=before, after=after)

    def update_children(self, *args, **kwargs) -> None:
        self.clear()
        self.add_children(*args, **kwargs)
    
    def remove_child(self, child: str | Widget) -> None:
        if isinstance(child, str):
            try:
                self.query_one(child).remove()
            except NoMatches as e:
                gptui_logger.error(e)
        else:
            child.remove()
    
    def remove_child_last(self) -> None:
        try:
            children = self.query("GridContentBase > *")
            children.last().remove()
        except NoMatches:
            return
    
    def remove_child_first(self):
        try:
            children = self.query("GridContentBase > *")
            children.first().remove()
        except NoMatches:
            return
    
    def clear(self):
        self.remove_children()

    def change_child_order(
        self,
        child,
        before: int | Widget | None = None,
        after: int | Widget | None = None
    ) -> None:
        self.move_child(child, before=before, after=after)


class MyCheckBox(Widget, Generic[CheckBoxPointer]):
    def __init__(self, status: bool, icon: Text, label: Text, pointer: CheckBoxPointer, domain=None, **kwargs):
        super().__init__(**kwargs)
        self.status = status
        self.icon = icon
        self.label = label
        self.pointer = pointer
        self.domain = domain

    def compose(self) -> ComposeResult:
        yield self.IconRegion(self.status, self.icon, self)
        yield self.LabelRegion(self.label, self)

    class IconRegion(Static):
        def __init__(self, status: bool, icon: Text, check_box_instance: MyCheckBox):
            super().__init__()
            self.status = status
            self.icon = icon
            self.check_box = check_box_instance
    
        def on_mount(self) -> None:
            self.display()

        def display(self):
            icon_display = Text()
            if self.status is True:
                if ThemeColor._theme == "monochrome":
                    icon_display.append_text(Text("◉", tc("green") or "green"))
                else:
                    icon_display.append_text(Text(u"\u2705"))
            else:
                if ThemeColor._theme == "monochrome":
                    icon_display.append_text(Text("○", tc("green") or "green"))
                else:
                    icon_display.append_text(Text(u"\u2B1C"))
            icon_display.append_text(self.icon)
            self.update(icon_display)
        
        def on_click(self):
            self.status = not self.status
            self.post_message(self.CheckBoxStatusChanged(self.status, self.check_box))
            self.display()
        
        class CheckBoxStatusChanged(Message):
            def __init__(self, status: bool, check_box: MyCheckBox) -> None:
                self.check_box = check_box
                self.status = status
                super().__init__()

    class LabelRegion(Static):
        def __init__(self, label: Text, check_box_instance: MyCheckBox):
            super().__init__()
            self.update(label)
            self.check_box = check_box_instance

        def on_click(self):
            self.post_message(self.CheckBoxLabelClicked(self.check_box))
        
        class CheckBoxLabelClicked(Message):
            def __init__(self, check_box: MyCheckBox) -> None:
                self.check_box = check_box
                super().__init__()


class FileIcon(Static, can_focus=True):
    
    DEFAULT_CSS = """
    FileIcon {
        width: 6;
    }
    FileIcon:focus {
        background: blue;
    }
    """

    BINDINGS = [
        ("space", "preview", "Preview the content of the file"),
    ]
    
    def __init__(self, pointer: Doc, file_label: str, file_type: str, file_description: str, previewer, **kwargs):
        super().__init__(**kwargs)
        icon_display = file_icon(file_label=file_label, file_type=file_type, file_description=file_description)
        self.update(icon_display)
        self.mydisplay = icon_display
        self.pointer = pointer
        self.previewer = previewer
    
    async def on_click(self):
        self.post_message(self.FileIconClicked(self, self.pointer))
        self.styles.opacity = 0.5
        self.styles.animate("opacity", value=1.0, duration=0.5)

    def action_preview(self):
        doc = self.pointer
        content = doc.content
        self.app.push_screen(MarkdownPreview(content, previewer_title=doc.name + doc.ext))

    class FileIconClicked(Message):
        def __init__(self, icon, pointer: Doc) -> None:
            self.icon = icon
            self.pointer = pointer
            super().__init__()


class SlideSwitch(Widget):
    DEFAULT_CSS = """
    SliderSwitcher {
        width: 3;
    }
    """

    def __init__(self, sliders: list, index: int = 0, direction: str = "down", **kwargs):
        super().__init__(**kwargs)
        self.direction = direction
        self.index = index
        self.sliders = []
        for slider in sliders:
            self.sliders.append(self.Slider(slider[0], slider[1], self))
        self.set_sliders(index, refresh=False)

    def compose(self) -> ComposeResult:
        for slider in self.sliders:
            yield slider

    def on_slider_slider_changed(self, event):
        index = event.index
        self.index = index
        self.set_sliders(index)
    
    def change_to_index(self, index):
        slider = self.sliders[index]
        slider.on_click()

    def change_to_pointer(self, aim_pointer) -> None:
        index_list = self.query_pointer(aim_pointer)
        if len(index_list) != 1:
            gptui_logger.error("Match zero or more than one pointer.")
            return
        self.change_to_index(index_list[0])

    def query_pointer(self, aim_pointer) -> list:
        pointers_list = [slider.pointer for slider in self.sliders]
        result = [index for index, pointer in enumerate(pointers_list) if pointer == aim_pointer]
        return result

    def set_sliders(self, index, refresh: bool = True):
        if self.direction == "down":
            if index == 0:
                self.sliders[0].set_status("on_down_first", refresh=refresh)
                for slider in self.sliders[1:-1]:
                    slider.set_status("lower_down", refresh=refresh)
                self.sliders[-1].set_status("off_down_last", refresh=refresh)
            elif index == len(self.sliders) - 1:
                self.sliders[0].set_status("off_down_first", refresh=refresh)
                for slider in self.sliders[1:-1]:
                    slider.set_status("upper_down", refresh=refresh)
                self.sliders[-1].set_status("on_down_last", refresh=refresh)
            else:
                self.sliders[0].set_status("off_down_first", refresh=refresh)
                for slider in self.sliders[1:index]:
                    slider.set_status("upper_down", refresh=refresh)
                self.sliders[index].set_status("on_down", refresh=refresh)
                for slider in self.sliders[index+1:-1]:
                    slider.set_status("lower_down", refresh=refresh)
                self.sliders[-1].set_status("off_down_last", refresh=refresh)
        else:
            if index == 0:
                self.sliders[0].set_status("on_up_first", refresh=refresh)
                for slider in self.sliders[1:-1]:
                    slider.set_status("lower_up", refresh=refresh)
                self.sliders[-1].set_status("off_up_last", refresh=refresh)
            elif index == len(self.sliders) - 1:
                self.sliders[0].set_status("off_up_first", refresh=refresh)
                for slider in self.sliders[1:-1]:
                    slider.set_status("upper_up", refresh=refresh)
                self.sliders[-1].set_status("on_up_last", refresh=refresh)
            else:
                self.sliders[0].set_status("off_up_first", refresh=refresh)
                for slider in self.sliders[1:index]:
                    slider.set_status("upper_up", refresh=refresh)
                self.sliders[index].set_status("on_up", refresh=refresh)
                for slider in self.sliders[index+1:-1]:
                    slider.set_status("lower_up", refresh=refresh)
                self.sliders[-1].set_status("off_up_last", refresh=refresh)
    

    class Slider(Static, Generic[SliderPointer]):
        DEFAULT_CSS = """
        Slider {
            width: 3;
            height: 1;
        }
        """

        def __init__(self, label: Text | str, pointer: SliderPointer, slide_switch):
            super().__init__()
            self.status = None
            self.label = label
            self.pointer = pointer
            self.slide_switch = slide_switch

        def on_mount(self):
            self.display()

        def on_click(self):
            index = self.slide_switch.sliders.index(self)
            self.post_message(self.SliderChanged(self, self.pointer, index, self.slide_switch))

        def display(self):
            if isinstance(self.label, str):
                display_content = Text(self.label).copy()
            else:
                display_content = self.label.copy()
            if self.status in ("on_down", "on_up", "on_down_last", "on_down_first", "on_up_last", "on_up_first"):
                display_content.stylize(tc("red") or "red")
            if self.status == "on_down":
                display_content.append_text(Text("\u2501\u2513", tc("red") or "red"))
            elif self.status == "upper_down":
                display_content.append_text(Text("\u2574\u2502", tc("green") or "green"))
            elif self.status == "lower_down":
                display_content.append_text(Text("\u2574", tc("green") or "green"))
                display_content.append_text(Text("\u2503", tc("red") or "red"))
            elif self.status == "on_up":
                display_content.append_text(Text("\u2501\u251b", tc("red") or "red"))
            elif self.status == "upper_up":
                display_content.append_text(Text("\u2574", tc("green") or "green"))
                display_content.append_text(Text("\u2503", tc("red") or "red"))
            elif self.status == "lower_up":
                display_content.append_text(Text("\u2574\u2502", tc("green") or "green"))
            elif self.status == "on_down_last":
                display_content.append_text(Text("\u2501\u2501", tc("red") or "red"))
            elif self.status == "off_down_last":
                display_content.append_text(Text("\u2574", tc("green") or "green"))
                display_content.append_text(Text("\u2517", tc("red") or "red"))
            elif self.status == "on_down_first":
                display_content.append_text(Text("\u2501\u2513", tc("red") or "red"))
            elif self.status == "off_down_first":
                display_content.append_text(Text("\u2574\u2577", tc("green") or "green"))
            elif self.status == "on_up_first":
                display_content.append_text(Text("\u2501\u2501", tc("red") or "red"))
            elif self.status == "off_up_first":
                display_content.append_text(Text("\u2574", tc("green") or "green"))
                display_content.append_text(Text("\u250f", tc("red") or "red"))
            elif self.status == "on_up_last":
                display_content.append_text(Text("\u2501\u251b", tc("red") or "red"))
            elif self.status == "off_up_last":
                display_content.append_text(Text("\u2574\u2575", tc("green") or "green"))
            self.update(display_content)

        def set_status(self, status, refresh: bool = True):
            self.status = status
            if refresh is True:
                self.display()

        class SliderChanged(Message):
            def __init__(self, slider, pointer, index, slide_switch) -> None:
                self.slider = slider
                self.pointer = pointer
                self.index = index
                self.slide_switch = slide_switch
                super().__init__()


class MyMarkdownWindow(Widget, can_focus=True):
    
    DEFAULT_CSS = """
    MyMarkdownWindow {
        width: 50%;
        height: 50%;
        border: round;
    }
    """

    BINDINGS = [
        ("space", "quit", "Quit"),
    ]

    def __init__(self, markdown: str | None = None, title: str | None = None, *args, **kwargs):
        self.markdown = markdown
        self.title = title
        self.status = True
        super().__init__(*args, **kwargs)

    def on_mount(self) -> None:
        if self.title is not None:
            self.border_title = self.title
        self.border_subtitle = "Press 'space' to close this previewer"
    
    def compose(self) -> ComposeResult:
        yield Markdown(self.markdown)

    def action_quit(self) -> None:
        self.status = False

    @classmethod
    async def my_markdown_window(cls, parent: Widget, markdown: str, title: str | None = None, *args, **kwargs) -> None:
        markdown_window_instance = MyMarkdownWindow(markdown=markdown, title=title, classes = "top_layer", *args, **kwargs)
        await parent.mount(markdown_window_instance)
        markdown_window_instance.focus()
        while markdown_window_instance.status:
            await asyncio.sleep(0.1)
        markdown_window_instance.remove()


class _SelectPath(Widget):
    # Not used, switched to using SelectPathDialog by Screen. Kept as future reference.

    DEFAULT_CSS = """
    SelectPath {
        width: 40%;
        height: 50%;
        border: double;
    }
    #bottom {
        height: 3;
        align: center bottom;
    }
    Input {
        height: 1;
        border: solid gray;
    }
    #cancel {
        offset-x: -15%;
    }
    #confirm {
        offset-x: 15%;
    }
    """

    def __init__(self, label: str | Text = "", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.label = label
        self.status = True
        self.value = None

    def compose(self) -> ComposeResult:
        yield Label(self.label)
        yield Input(id="path")
        yield DirectoryTree("./user0", id="directory_tree")
        with Horizontal(id="bottom"):
            yield Button("Cancel", id="cancel")
            yield Button("Confirm", id="confirm")

    def on_button_pressed(self, event) -> None:
        if event.button.id == "confirm":
            self.value = self.query_one("#path").value
            self.status = False
        elif event.button.id == "cancel":
            self.value = None
            self.status = False

    async def on_input_submitted(self, message) -> None:
        self.value = message.value
        self.status = False

    def on_directory_tree_file_selected(self, event) -> None:
        self.query_one("#path").value = str(os.path.dirname(event.path)) + "/"

    @classmethod
    async def select_path(
        cls,
        parent: Widget,
        callback: Callable[[str], None] | Callable[[str], Awaitable[None]],
        label: str | Text = "",
        *args,
        **kwargs
    ) -> None:
        _instance = _SelectPath(label=label, classes="top_layer", *args, **kwargs)
        await parent.mount(_instance)
        while _instance.status:
            await asyncio.sleep(0.1)
        value = _instance.value
        _instance.remove()
        if value is not None:
            if inspect.iscoroutinefunction(callback):
                await callback(value)
            elif callable(callback):
                callback(value)
            else:
                raise ValueError("Callback must be callable or a coroutine function")


class AppStart(Widget):
    
    DEFAULT_CSS = """
    AppStart {
        border: none;
    }
    AppStart RichLog {
        overflow: auto auto;
        scrollbar-size: 1 1;
        background: black;
    }
    AppStart Static {
        height: 14;
        text-align: center;
        background: black;
    }
    """

    def __init__(self, my_app, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.my_app = my_app

    def compose(self) -> ComposeResult:
        self.static = Static()
        yield self.static
        self.rich_log = RichLog(highlight=True, markup=True)
        yield self.rich_log
    
    def on_show(self):
        width = self.static.content_size.width
        if width >= 50:
            text = Text(
                textwrap.dedent(
                    """
                      $$$$$$\\  $$$$$$$\\ $$$$$$$$\\ $$\\   $$\\ $$$$$$\\ 
                      $$  __$$\\ $$  __$$ \\__$$  __|$$ |  $$ |\\_$$  _|
                    $$ /  \\__|$$ |  $$ |  $$ |   $$ |  $$ |  $$ |  
                    $$ |$$$$\\ $$$$$$$  |  $$ |   $$ |  $$ |  $$ |  
                    $$ |\\_$$ |$$  ____/   $$ |   $$ |  $$ |  $$ |  
                    $$ |  $$ |$$ |        $$ |   $$ |  $$ |  $$ |  
                     \\$$$$$$  |$$ |        $$ |   \\$$$$$$  |$$$$$$\\ 
                       \\______/ \\__|        \\__|    \\______/ \\______|
                    """
                )
            )
            text += Text(f"\nVersion: {self.my_app.app_version}\n")
            text += Text("Copyright (c) 2023 happyapplehorse\n")
            text += Text("e-mail: chaoxueao@gmial.com\n")
            text += Text("Note: Voices in this app are AI-generated, not human-spoken.\n")
            text += "-" * width
            self.static.update(text)
        else:
            self.static.remove()
    
    def get_rich_log(self):
        return self.rich_log

    def set_init_func(self, func: Coroutine):
        self.init_func = func

    async def app_init(self) -> bool:
        status = await self.init_func
        if status is False:
            return False
        self.static.update("")
        self.rich_log.clear()
        height = self.my_app.size.height
        self.animate("offset", value=Offset(0, height), duration=0.7, easing="linear")
        await asyncio.sleep(0.7)
        self.remove()
        return True


class NoPaddingButton(Button):
    def render(self) -> TextType:
        label = Text.assemble(self.label)
        label.stylize(self.text_style)
        return label
