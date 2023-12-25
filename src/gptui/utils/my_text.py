import logging
import re
from typing import Iterable, Optional, Tuple, List, Iterator, Union, overload, TYPE_CHECKING
from itertools import zip_longest

from rich.text import Text
from rich.containers import Lines
from rich.text import Span
from rich.console import Console
from rich._pick import pick_bool
from rich.cells import cell_len, chop_cells
from rich._loop import loop_last
from rich.containers import Lines


gptui_logger = logging.getLogger("gptui_logger")

if TYPE_CHECKING: # pragma: no cover
    from rich.console import Console, JustifyMethod, OverflowMethod, ConsoleOptions, RenderResult

DEFAULT_JUSTIFY: "JustifyMethod" = "default"
DEFAULT_OVERFLOW: "OverflowMethod" = "fold"


class MyText(Text):

    def copy(self) -> "MyText":
            """Return a copy of this instance."""
            copy_self = MyText(
                self.plain,
                style=self.style,
                justify=self.justify,
                overflow=self.overflow,
                no_wrap=self.no_wrap,
                end=self.end,
                tab_size=self.tab_size,
            )
            copy_self._spans[:] = self._spans
            return copy_self
    
    def blank_copy(self, plain: str = "") -> "MyText":
        """Return a new Text instance with copied meta data (but not the string or spans)."""
        copy_self = MyText(
            plain,
            style=self.style,
            justify=self.justify,
            overflow=self.overflow,
            no_wrap=self.no_wrap,
            end=self.end,
            tab_size=self.tab_size,
        )
        return copy_self

    # TODO: check MyText completeness
    def join(self, lines: Iterable["MyText"]) -> "MyText":
            """Join text together with this instance as the separator.

            Args:
                lines (Iterable[Text]): An iterable of Text instances to join.

            Returns:
                Text: A new text instance containing join text.
            """

            new_text = self.blank_copy()

            def iter_text() -> Iterable["MyText"]:
                if self.plain:
                    for last, line in loop_last(lines):
                        yield line
                        if not last:
                            yield self
                else:
                    yield from lines

            extend_text = new_text._text.extend
            append_span = new_text._spans.append
            extend_spans = new_text._spans.extend
            offset = 0
            _Span = Span

            for text in iter_text():
                extend_text(text._text)
                if text.style:
                    append_span(_Span(offset, offset + len(text), text.style))
                extend_spans(
                    _Span(offset + start, offset + end, style)
                    for start, end, style in text._spans
                )
                offset += len(text)
            new_text._length = offset
            return new_text
    
    def split(
        self,
        separator: str = "\n",
        *,
        include_separator: bool = False,
        allow_blank: bool = False,
    ) -> "MyLines":
        """Split rich text in to lines, preserving styles.

        Args:
            separator (str, optional): String to split on. Defaults to "\\\\n".
            include_separator (bool, optional): Include the separator in the lines. Defaults to False.
            allow_blank (bool, optional): Return a blank line if the text ends with a separator. Defaults to False.

        Returns:
            List[MyText]: A list of rich text, one per line of the original.
        """
        assert separator, "separator must not be empty"

        text = self.plain
        if separator not in text:
            return MyLines([self.copy()])

        if include_separator:
            lines = self.divide(
                match.end() for match in re.finditer(re.escape(separator), text)
            )
        else:

            def flatten_spans() -> Iterable[int]:
                for match in re.finditer(re.escape(separator), text):
                    start, end = match.span()
                    yield start
                    yield end

            lines = MyLines(
                line for line in self.divide(flatten_spans()) if line.plain != separator
            )

        if not allow_blank and text.endswith(separator):
            lines.pop()

        return lines

    # fix IndexError bug in Text.split() method.
    def divide(self, offsets: Iterable[int]) -> "MyLines":
        """Divide text in to a number of lines at given offsets.

        Args:
            offsets (Iterable[int]): Offsets used to divide text.

        Returns:
            MyLines: New MyText instances between offsets.
        """
        _offsets = list(offsets)

        if not _offsets:
            return MyLines([self.copy()])

        text = self.plain
        text_length = len(text)
        divide_offsets = [0, *_offsets, text_length]
        line_ranges = list(zip(divide_offsets, divide_offsets[1:]))

        style = self.style
        justify = self.justify
        overflow = self.overflow
        _MyText = MyText
        new_lines = MyLines(
            _MyText(
                text[start:end],
                style=style,
                justify=justify,
                overflow=overflow,
            )
            for start, end in line_ranges
        )
        if not self._spans:
            return new_lines

        _line_appends = [line._spans.append for line in new_lines._lines]
        line_count = len(line_ranges)
        _Span = Span

        for span_start, span_end, style in self._spans:

            lower_bound = 0
            upper_bound = line_count
            start_line_no = (lower_bound + upper_bound) // 2

            while True:
                line_start, line_end = line_ranges[start_line_no]
                if span_start < line_start:
                    upper_bound = start_line_no - 1
                elif span_start > line_end:
                    lower_bound = start_line_no + 1
                else:
                    break
                start_line_no = (lower_bound + upper_bound) // 2
                # fix IndexError bug in Text.split() method.
                if start_line_no >= line_count:
                    start_line_no = line_count - 1
                    break

            if span_end < line_end:
                end_line_no = start_line_no
            else:
                end_line_no = lower_bound = start_line_no
                upper_bound = line_count

                while True:
                    line_start, line_end = line_ranges[end_line_no]
                    if span_end < line_start:
                        upper_bound = end_line_no - 1
                    elif span_end > line_end:
                        lower_bound = end_line_no + 1
                    else:
                        break
                    end_line_no = (lower_bound + upper_bound) // 2
                    # fix IndexError bug in Text.split() method.
                    if end_line_no >= line_count:
                        end_line_no = line_count - 1
                        break

            for line_no in range(start_line_no, end_line_no + 1):
                line_start, line_end = line_ranges[line_no]
                new_start = max(0, span_start - line_start)
                new_end = min(span_end - line_start, line_end - line_start)
                if new_end > new_start:
                    _line_appends[line_no](_Span(new_start, new_end, style))

        return new_lines

    # improve support for line wraps in Chinese
    def wrap(
            self,
            console: "Console",
            width: int,
            *,
            justify: Optional["JustifyMethod"] = None,
            overflow: Optional["OverflowMethod"] = None,
            tab_size: int = 8,
            no_wrap: Optional[bool] = None,
        ) -> "MyLines":
            """Word wrap the text.

            Args:
                console (Console): Console instance.
                width (int): Number of characters per line.
                emoji (bool, optional): Also render emoji code. Defaults to True.
                justify (str, optional): Justify method: "default", "left", "center", "full", "right". Defaults to "default".
                overflow (str, optional): Overflow method: "crop", "fold", or "ellipsis". Defaults to None.
                tab_size (int, optional): Default tab size. Defaults to 8.
                no_wrap (bool, optional): Disable wrapping, Defaults to False.

            Returns:
                MyLines: Number of lines.
            """
            wrap_justify = justify or self.justify or DEFAULT_JUSTIFY
            wrap_overflow = overflow or self.overflow or DEFAULT_OVERFLOW

            no_wrap = pick_bool(no_wrap, self.no_wrap, False) or overflow == "ignore"

            lines = MyLines()
            for line in self.split(allow_blank=True):
                if "\t" in line:
                    line.expand_tabs(tab_size)
                if no_wrap:
                    new_lines = MyLines([line])
                else:
                    offsets = my_divide_line(str(line), width, fold=wrap_overflow == "fold")
                    new_lines = line.divide(offsets)
                for line in new_lines:
                    line.rstrip_end(width)
                if wrap_justify:
                    new_lines.justify(
                        console, width, justify=wrap_justify, overflow=wrap_overflow
                    )
                for line in new_lines:
                    line.truncate(width, overflow=wrap_overflow)
                lines.extend(new_lines)
            return lines


# to use MyText
class MyLines(Lines):
    """A list subclass which can render to the console."""

    def __init__(self, lines: Iterable["MyText"] = ()) -> None:
        self._lines: List["MyText"] = list(lines)

    def __repr__(self) -> str:
        return f"Lines({self._lines!r})"

    def __iter__(self) -> Iterator["MyText"]:
        return iter(self._lines)

    @overload
    def __getitem__(self, index: int) -> "MyText":
        ...

    @overload
    def __getitem__(self, index: slice) -> List["MyText"]:
        ...

    def __getitem__(self, index: Union[slice, int]) -> Union["MyText", List["MyText"]]:
        return self._lines[index]

    def __setitem__(self, index: int, value: "MyText") -> "Lines":
        self._lines[index] = value
        return self

    def __len__(self) -> int:
        return self._lines.__len__()

    def __rich_console__(
        self, console: "Console", options: "ConsoleOptions"
    ) -> "RenderResult":
        """Console render method to insert line-breaks."""
        yield from self._lines

    def append(self, line: "MyText") -> None:
        self._lines.append(line)

    def extend(self, lines: Iterable["MyText"]) -> None:
        self._lines.extend(lines)

    def pop(self, index: int = -1) -> "MyText":
        return self._lines.pop(index)

    def justify(
        self,
        console: "Console",
        width: int,
        justify: "JustifyMethod" = "left",
        overflow: "OverflowMethod" = "fold",
    ) -> None:
        """Justify and overflow text to a given width.

        Args:
            console (Console): Console instance.
            width (int): Number of characters per line.
            justify (str, optional): Default justify method for text: "left", "center", "full" or "right". Defaults to "left".
            overflow (str, optional): Default overflow for text: "crop", "fold", or "ellipsis". Defaults to "fold".

        """
        #from .text import Text

        if justify == "left":
            for line in self._lines:
                line.truncate(width, overflow=overflow, pad=True)
        elif justify == "center":
            for line in self._lines:
                line.rstrip()
                line.truncate(width, overflow=overflow)
                line.pad_left((width - cell_len(line.plain)) // 2)
                line.pad_right(width - cell_len(line.plain))
        elif justify == "right":
            for line in self._lines:
                line.rstrip()
                line.truncate(width, overflow=overflow)
                line.pad_left(width - cell_len(line.plain))
        elif justify == "full":
            for line_index, line in enumerate(self._lines):
                if line_index == len(self._lines) - 1:
                    break
                words = line.split(" ")
                words_size = sum(cell_len(word.plain) for word in words)
                num_spaces = len(words) - 1
                spaces = [1 for _ in range(num_spaces)]
                index = 0
                if spaces:
                    while words_size + num_spaces < width:
                        spaces[len(spaces) - index - 1] += 1
                        num_spaces += 1
                        index = (index + 1) % len(spaces)
                tokens: List[MyText] = []
                for index, (word, next_word) in enumerate(
                    zip_longest(words, words[1:])
                ):
                    tokens.append(word)
                    if index < len(spaces):
                        style = word.get_style_at_offset(console, -1)
                        next_style = next_word.get_style_at_offset(console, 0)
                        space_style = style if style == next_style else line.style
                        tokens.append(MyText(" " * spaces[index], style=space_style))
                self[line_index] = MyText("").join(tokens)


re_word = re.compile(r"\s*([\u4e00-\u9fef][，；。：？！]*|[^\u4e00-\u9fef\s]+)\s*")

def words(text: str) -> Iterable[Tuple[int, int, str]]:
    position = 0
    word_match = re_word.match(text, position)
    while word_match is not None:
        start, end = word_match.span()
        word = word_match.group(0)
        yield start, end, word
        word_match = re_word.match(text, end)

# This function has not been modified; it was moved as is to utilize the custom 'words' function.
def my_divide_line(text: str, width: int, fold: bool = True) -> list[int]:
    """Given a string of text, and a width (measured in cells), return a list
    of cell offsets which the string should be split at in order for it to fit
    within the given width.

    Args:
        text: The text to examine.
        width: The available cell width.
        fold: If True, words longer than `width` will be folded onto a new line.

    Returns:
        A list of indices to break the line at.
    """
    break_positions: list[int] = []  # offsets to insert the breaks at
    append = break_positions.append
    cell_offset = 0
    _cell_len = cell_len

    for start, _end, word in words(text):
        word_length = _cell_len(word.rstrip())
        remaining_space = width - cell_offset
        word_fits_remaining_space = remaining_space >= word_length

        if word_fits_remaining_space:
            # Simplest case - the word fits within the remaining width for this line.
            cell_offset += _cell_len(word)
        else:
            # Not enough space remaining for this word on the current line.
            if word_length > width:
                # The word doesn't fit on any line, so we can't simply
                # place it on the next line...
                if fold:
                    # Fold the word across multiple lines.
                    folded_word = chop_cells(word, width=width)
                    for last, line in loop_last(folded_word):
                        if start:
                            append(start)
                        if last:
                            cell_offset = _cell_len(line)
                        else:
                            start += len(line)
                else:
                    # Folding isn't allowed, so crop the word.
                    if start:
                        append(start)
                    cell_offset = _cell_len(word)
            elif cell_offset and start:
                # The word doesn't fit within the remaining space on the current
                # line, but it *can* fit on to the next (empty) line.
                append(start)
                cell_offset = _cell_len(word)

    return break_positions
