from rich.console import Console

from .my_text import MyText


def my_line_count(content: MyText, width: int, console=Console()) -> int:
    lines = content.split(allow_blank=True)
    num_count = 0
    for line in lines:
        num_count += len(line.wrap(console, width))
    return num_count
