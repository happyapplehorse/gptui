import logging

from .my_text import MyText as Text
from ..views.theme import theme_color as tc

gptui_logger = logging.getLogger("gptui_logger")


def file_icon(
    file_label: str,
    file_type: str,
    file_description: str,
    icon_color: str | None = None,
    description_color: str | None = None,
) -> Text:
    icon_color = icon_color or tc("yellow") or "yellow"
    description_color = description_color or tc("white") or "white"

    display = Text('', icon_color)
    if file_type == ".txt":
        display += Text('\u2595'+'\u2056\u0305'+'\u2056\u0305'+'\u2056\u0305'+'\u2572'+' \n')
        display += Text('\u2595'+f'{file_label[:3]}'+'\u2595'+' \n'+'\u2595')
        display += Text('txt\u2595', 'underline')
    elif file_type == ".md":
        display += Text('\u2595'+' \u0305'+'\ueb1d\u0305'+' \u0305'+'\u2572'+' \n')
        display += Text('\u2595'+f'{file_label[:3]}'+'\u2595'+' \n'+'\u2595')
        display += Text('.md\u2595', 'underline')
    elif file_type == ".bin":
        display += Text('\u2595'+'l\u0305'+'l\u0305'+'l\u0305'+'l\u0305'+'l\u0305'+'l\u0305'+'l\u0305'+'\u2572'+' \n')
        display += Text('\u2595'+f'{file_label[:3]}'+'\u2595'+' \n'+'\u2595')
        display += Text('bin\u2595', 'underline')
    elif file_type == ".json":
        display += Text('\u2595'+' \u0305'+'{\u0305'+' \u0305'+'}\u0305'+'\u2572'+' \n')
        display += Text('\u2595'+f'{file_label[:3]}'+'\u2595'+' \n'+'\u2595')
        display += Text('jsn\u2595', 'underline')
    elif file_type == ".py":
        display += Text('\u2595'+' \u0305'+'\ue606\u0305'+' \u0305'+'\u2572'+' \n')
        display += Text('\u2595'+f'{file_label[:3]}'+'\u2595'+' \n'+'\u2595')
        display += Text('.\uf820 \u2595', 'underline')
    elif file_type == ".sh":
        display += Text('\u2595'+'<\u0305'+'\u29f8\u0305'+'>\u0305'+'\u2572'+' \n')
        display += Text('\u2595'+f'{file_label[:3]}'+'\u2595'+' \n'+'\u2595')
        display += Text('.sh\u2595', 'underline')
    else:
        file_type += '   '
        display += Text('\u2595'+'\u203e'+'\u203e'+'\u203e'+'\u29f9'+' \n')
        display += Text('\u2595'+f'{file_label[:3]}'+'\u2595'+' \n'+'\u2595')
        display += Text(f'{file_type[:3]}\u2595', 'underline')
    if len(file_description) > 12:
        description_line0 = file_description[:6] + '\n'
        description_line1 = '\u2026' + file_description[-5:] + '\n'
    else:
        file_description = file_description.ljust(12)
        description_line0 = file_description[:6] + '\n'
        description_line1 = file_description[6:] + '\n'
    description = Text(' \n' + description_line0 + description_line1, f'{description_color}')
    out_display = display + description
    return out_display
