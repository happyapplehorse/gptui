import copy
import logging
import re
import os
from typing import Self

from pygments import highlight
from pygments.lexers import get_lexer_by_name, ClassNotFound
from pygments.formatters import TerminalTrueColorFormatter
from rich.console import Console
from rich.style import Style

from ..views.theme import theme_color as tc
from ..utils.file_icon import file_icon
from ..utils.my_text import MyText as Text
from ..utils.my_text import MyLines as Lines


gptui_logger = logging.getLogger("gptui_logger")


class DecorateDisplay:
    def __init__(self, app):
        self.app = app
        self.code_block_list = []
        self.chain_lines: Lines | None = None
        self.chain_length_list: list | None = None
        self.chain_max_width: int | None = None
    
    def pre_wrap_and_highlight(
        self,
        inp_string: str,
        stream: bool = False,
        copy_code: bool = False,
        wrap: dict | None = None,
    ) -> Text:
        """Wrap and highlight a string that might contain a file.

        if 'file_wrap["wrap"]' is False:
            return wraped string (Text) such as:
                content before file start
                ******************** FILE CONTENT BEGIN ********************
                ===== Document #1 text.txt =====

                This is the content of the document #1.


                ==========================

                ===== Document #2 test.txt =====

                This is the content of the the file #2.


                ===========================
                ******************** FILE CONTENT FINISH *******************
                content after file end

        if 'file_wrap["wrap"]' is True:
            return wraped string (Text) such as:
                content before file start
                ******************** FILE CONTENT BEGIN ********************
                FILE_ICON1 FILE_ICON2 (Actually displayed as rendered icons)
                ******************** FILE CONTENT FINISH *******************
                content after file end
        
        Args:
            inp_string:
            stream: Whether in stream mode?
            copy_code:
                Specify whether to enable the copy_code feature for this operation.
                In a streaming display, the copy_code feature should only be enabled for the last instance.
            wrap (dict): Wrap parameters. It can include the following key-value strcture.
                file_wrap: File wrap parameters.
                    wrap (bool): Whether wrap file content into a file icon.
                    wrap_num (int): Icon numbers in each line.
                words_color: Specify the color of the text, excluding the file icons.
            
        Example:
            wrap={"file_wrap": {"wrap: True", "wrap_num": 4}, "words_color": "white"}
        """
        wrap = wrap or {"file_wrap": {"wrap": True, "wrap_num": 4}, "words_color": tc("white") or "white"}
        
        file_wrap = wrap.get("file_wrap", {"wrap":True, "wrap_num":4})
        wrap_bool = file_wrap["wrap"]
        wrap_num = file_wrap["wrap_num"]
        words_color = wrap.get("words_color", tc("white") or "white")
        if wrap_bool is True:
            out = self.wrap_files_in_string(extract_files_from_string(inp_string), wrap_num=wrap_num, stream=stream, copy_code=copy_code, words_color=words_color)
            return out
        else:
            file_start_flag = "******************** FILE CONTENT BEGIN ********************"
            file_end_flag = "******************** FILE CONTENT FINISH *******************"
            out_string_list = []
            start = 0
            while True:
                file_start = inp_string.find(file_start_flag, start)
                if file_start == -1:
                    # This is content after 'file_end_flag' or there is no file block
                    out_string_list.append(self.highlight_code_block_from_plain_text(inp_string[start:], stream=stream, copy_code=copy_code, words_color=words_color))
                    break
                # This is content before file begin
                out_string_list.append(self.highlight_code_block_from_plain_text(inp_string[start:file_start], stream=stream, copy_code=copy_code, words_color=words_color))
                # file begin flag
                out_string_list.append(Text(file_start_flag, tc("cyan") or "cyan"))
                start = file_start + len(file_start_flag)
                file_end = inp_string.find(file_end_flag, start)
                if file_end == -1:
                    out_string_list.append(self.highlight_code_block_from_plain_text(inp_string[start:], stream=stream, copy_code=copy_code, words_color=words_color))
                    break
                # content in file block
                out_string_list.append(self.highlight_code_block_from_plain_text(inp_string[start:file_end], stream=stream, copy_code=copy_code, words_color=words_color))
                # file finish flag
                out_string_list.append(Text(file_end_flag, tc("cyan") or "cyan"))
                start = file_end + len(file_end_flag)

            out_string = Text('').join(out_string_list)
            return out_string

    def wrap_files_in_string(
        self,
        string_data: list,
        wrap_num: int = 4,
        stream: bool = False,
        copy_code: bool = False,
        words_color: str | None = None,
    ) -> Text:
        """Translate the content within the string to the corresponding file icon.
        
        Args:
            string_data: Output of extract_files_from_string.
            wrap_num: Icon numbers in each line.
            stream: Whether in stream mode?
            copy_code:
                Switch in highlight_code_block_from_plain_text.
            words_color: Specify the color of the text outside of files.
        """
        words_color = words_color or tc("white") or "white"
        part_list = []

        def group_files_icon_by(files_icon: list, wrap_num: int) -> Text:
            out_lines = []
            icons = [icon.split() for icon in files_icon]
            for i in range(0, len(files_icon), wrap_num):
                lines = [Text(' ').join(line) for line in zip(*icons[i:i+wrap_num])]
                out_lines.extend(lines)
            out = Text('\n').join(out_lines) + Text('\n')
            return out

        for part in string_data:
            if isinstance(part, str):
                if part:
                    part_list.append(self.highlight_code_block_from_plain_text(part, stream=stream, copy_code=copy_code, words_color=words_color))
            else:
                files_icon = []
                for file_name in part:
                    file_label, file_ext = os.path.splitext(file_name)
                    file_icon_string = file_icon(file_label=file_label, file_type=file_ext, file_description=file_name, icon_color="yellow")
                    files_icon.append(file_icon_string)
                
                files_text = Text("\n******************** FILE CONTENT BEGIN ********************\n", tc("cyan") or "cyan")\
                    + group_files_icon_by(files_icon, wrap_num=wrap_num) + \
                    Text("******************** FILE CONTENT FINISH *******************\n", tc("cyan") or "cyan")
                part_list.append(files_text)

        return Text('\n').join(part_list)

    def highlight_code_block_from_plain_text(
        self,
        inp_string: str,
        stream: bool = False,
        copy_code: bool = False,
        words_color: str | None = None,
    ) -> Text:
        words_color = words_color or tc("white") or "white"
        output_text = Text()
        while True:
            # Find the start of a code block, indicated by "```".
            code_start = inp_string.find("```")
            if code_start == -1:
                output_text.append_text(Text(inp_string, words_color))
                break
            # Find the end of the language specifier in the code block, which ends with a newline.
            lang_end = inp_string.find("\n", code_start + 3)
            if lang_end == -1:
                output_text.append_text(Text(inp_string, words_color))
                break
            # Find the end of the code block, indicated by another "```".
            code_end = inp_string.find("```", lang_end + 1)
            if code_end == -1:
                if stream:
                    code_end = len(inp_string)
                else:
                    output_text.append_text(Text(inp_string, words_color))
                    break
            # Append any text before the code block to the output text.
            output_text.append_text(Text(inp_string[:code_start], words_color))
            # Extract the language specifier.
            lang = inp_string[code_start+3:lang_end].strip()
            # Try to get a Pygments lexer for this language.
            try:
                lexer = get_lexer_by_name(lang)
            except ClassNotFound:
                # If the language is not found, no lexer is available.
                lexer = None
            # If a lexer is found, highlight the code block.
            if lexer is not None:
                # language name display
                lang_display = ' ' + lang + ' '
                lang_display_text = Text(lang_display.upper(), f"reverse italic bold {tc('white') or 'white'}")
                if copy_code:
                    action_string = f"app.copy_code({len(self.code_block_list)})"
                    lang_display_text.on(click=action_string)
                output_text.append_text(lang_display_text + Text('\n'))

                # Create a formatter with a specific style.
                formatter = TerminalTrueColorFormatter(style="material")
                # Extract the code from the code block.
                code = inp_string[lang_end+1:code_end].strip()
                # Use Pygments to highlight the code, which will return an ANSI string.
                ansi_text = highlight(code, lexer, formatter)
                # Create a Text object from the ANSI string and append it to the output text.
                output_text.append_text(Text.from_ansi(ansi_text))
                # add the code to code_block_list to be copied
                if copy_code:
                    self.code_block_list.append(code)
            # If no lexer is found, append the unhighlighted code block to the output text.
            else:
                output_text.append_text(Text(inp_string[code_start:code_end], words_color))
            # Update the inp string to the remaining unprocessed string.
            inp_string = inp_string[code_end+3:]
        
        return output_text

    def text_to_lines_chain(self, inp: Text, container_width: int) -> Self:
        """Convert the Text object into a Lines object.
        
        This operation is a chainable operation.
        
        Args:
            inp: The Text object that needs to be converted.
            container_width: Specify the width of the display area.

        Returns:
            Self
        """
        console = Console()
        total_lines = Lines()
        lines = inp.split(allow_blank=True)
        for line in lines:
            lin = line.wrap(console=console, width=container_width, overflow="fold", no_wrap=False)
            total_lines.extend(lin)
        length_list = list(map(lambda line: line.cell_len, total_lines))
        max_width = max(length_list)
        self.chain_lines = total_lines
        self.chain_length_list = length_list
        self.chain_max_width = max_width
        return self

    def background_chain(
        self,
        inp: Text,
        container_width: int,
        background_color = None
    ) -> Self:
        """Add a background color to the specified content.

        This operation is a chainable operation.
        
        Args:
            inp: The content that needs background color.
            container_width: Specify the width of the display area.
            background_color: Specify the color.
        
        Returns:
            Self
        """
        console = Console()
        total_lines = Lines()
        lines = inp.split(allow_blank=True)
        for line in lines:
            lin = line.wrap(console=console, width=container_width, overflow="fold", no_wrap=False)
            total_lines.extend(lin)
        length_list = list(map(lambda line: line.cell_len, total_lines))
        max_width = max(length_list)
        out = Lines()
        for i, line in enumerate(total_lines):
            line.pad_right(max_width-length_list[i], character=' ')
            if background_color:
                line.stylize(Style(bgcolor=background_color))
            out.append(line)
        self.chain_lines = out
        self.chain_length_list = length_list
        self.chain_max_width = max_width
        return self

    def panel_chain(
        self,
        panel_color: str,
        line_type: int = 3
    ) -> Self:
        """Add a border around the given content to make it a rectangular panel.

        This operation is a chainable operation.
        
        Args:
            panel_color: Specify the color of the panel.
            line_type: Type of the border line.
                0:
                    ╭──────────╮
                    │          │
                    │          │
                    ╰──────────╯
                1:
                    ╭─ ── ── ──╮
                    |          |
                    |          |
                    ╰─ ── ── ──╯
                2:
                    ╭─ ─ ─ ─ ─ ╮
                    ╵          ╵
                    ╵          ╵
                    ╰─ ─ ─ ─ ─ ╯
                3:
                    ╭----------╮
                    ┆          ┆
                    ┆          ┆
                    ╰----------╯
        
        Returns:
            Self
        """
        out = Lines()
        assert self.chain_lines is not None, "self.chain_lines can not be None"
        assert self.chain_length_list is not None, "self.chain_length_list can not be None"
        assert self.chain_max_width is not None, "self.chain_max_width can not be None"
        max_width = self.chain_max_width
        if line_type == 0:
            horizental = u'\u2500' * max_width
            vertical = u'\u2502'
        elif line_type == 1:
            group = u'\u2500' + ' ' + u'\u2500'
            group_num, rest_num = divmod(max_width, 3)
            horizental = group * group_num + group[:rest_num]
            vertical = '|'
        elif line_type == 2:
            group = u'\u2500' + ' '
            group_num, rest_num = divmod(max_width, 2)
            horizental = group * group_num + group[:rest_num]
            vertical = u'\u2575'
        elif line_type == 3:
            horizental = '-' * max_width
            vertical = u'\u2506'
        else:
            horizental = '-' * max_width
            vertical = u'\u2506'
        top = Text(u'\u256D' + horizental + u'\u256E', panel_color)
        bottom = Text(u'\u2570' + horizental + u'\u256F', panel_color)
        out.append(top)
        for line in self.chain_lines:
            line = Text(vertical, panel_color) + line + Text(vertical, panel_color)
            out.append(line)
        out.append(bottom)
        self.chain_lines = out
        self.chain_length_list = [max_width + 2] * (len(self.chain_length_list) + 2)
        self.chain_max_width = max_width + 2
        return self

    def indicator_chain(self, indicator_color: str) -> Self:
        """Add an indicator to the left of the given content.

        This operation is a chainable operation.
        The indicator occupies the width of three characters.
        The inp Lines object should be content that has already been calculated considering the width.

        Args:
            indicator_color: Specify the indicator color.

        Returns:
            Self
        """
        first_time = True
        out = Lines()
        assert self.chain_lines is not None, "self.chain_lines can not be None"
        assert self.chain_length_list is not None, "self.chain_length_list can not be None"
        assert self.chain_max_width is not None, "self.chain_max_width can not be None"
        for line in self.chain_lines:
            if first_time:
                out.append(Text(u'\u251c'+u'\u2500'+' ', indicator_color).append_text(line))
                first_time = False
            else:
                out.append(Text(u'\u2502' + '  ', indicator_color).append_text(line))
        self.chain_lines = out
        self.chain_length_list = [length + 3 for length in self.chain_length_list]
        self.chain_max_width += 3
        return self
    
    def indicator(self, inp: Text, displayer_width: int, indicator_color: str) -> Lines:
        """Add an indicator to the left of the given Text.

        The indicator occupies the width of three characters,
        and the text content will be displayed with a width of displayer_width-3.
        Any part exceeding this width will be automatically folded.

        Args:
            inp: Content that requires an indicator.
            displayer_width: The width of the displayer.
            indicator_color: Specify the indicator color.

        Returns:
            Line object.
        """
        console = Console()
        total_lines = Lines()
        lines = inp.split(allow_blank=True)
        for line in lines:
            lin = line.wrap(console=console, width=displayer_width-3, overflow="fold", no_wrap=False)
            total_lines.extend(lin)
        first_time = True
        out = Lines()
        for line in total_lines:
            if first_time:
                out.append(Text(u'\u251c'+u'\u2500'+' ', indicator_color).append_text(line))
                first_time = False
            else:
                out.append(Text(u'\u2502' + '  ', indicator_color).append_text(line))
        return out

    def action_copy_code(self, index: int) -> None:
        content = self.code_block_list[index]
        self.app.drivers.copy_code(content)

    def clear_code_block(self) -> None:
        self.code_block_list = []

    def get_and_reset_chain(self) -> dict:
        result = {"lines": copy.copy(self.chain_lines), "length_list": copy.copy(self.chain_length_list), "max_width": self.chain_max_width}
        self.chain_lines = None
        self.chain_length_list = None
        self.chain_max_width = None
        return result


def extract_files_from_string(inp_string: str) -> list:
    """Extract files info from a string might contain files.
    Return a list in order. For content outside of each file block, return its original string.
    For each file block, return a tuple where the contents of the tuple are the filenames within the file block.
    """

    result = []
    file_blocks = re.split(r'(\*{20} FILE CONTENT BEGIN \*{20}|\*{20} FILE CONTENT FINISH \*{19})', inp_string)
    
    inside_file_block = None
    for block in file_blocks:
        if block == '*' * 20 + " FILE CONTENT BEGIN " + '*' * 20:
            inside_file_block = True
            continue
        elif block == '*' * 20 + " FILE CONTENT FINISH " + '*' * 19:
            inside_file_block = False
            continue

        if inside_file_block is True:
            file_titles = re.findall(r'===== Document #\d+ (.*?) =====', block)
            result.append(tuple(file_titles))
        else:
            result.append(block)
    
    return result
