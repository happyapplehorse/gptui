from typing import NamedTuple, Literal


ThemeName = Literal["default", "monochrome"]


class ColorMap(NamedTuple):
    name: str
    color: str


class ThemeColor:
    color_map: dict[str, str] = {}
    _theme: ThemeName = "default"

    @classmethod
    def insert_color_map(cls, name: str, color: str):
        cls.color_map[name] = color

    @classmethod
    def insert_color_map_batch(cls, color_map_list: list[ColorMap]) -> None:
        for color_map in color_map_list:
            cls.color_map[color_map.name] = color_map.color

    @classmethod
    def get_theme_color(cls, name: str) -> str | None:
        if name in cls.color_map:
            return cls.color_map[name]
        if cls._theme == "default":
            return None
        elif cls._theme == "monochrome":
            return "#5CE495" # responding to $success-lighten-2 in textual
        else:
            return None

    @classmethod
    def set_theme(cls, theme: ThemeName) -> None:
        cls._theme = theme
        if theme == "monochrome":
            ThemeColor.color_map["user_message"] = "#2E724B"
            ThemeColor.color_map["assistant_message"] = "#5CE495"
            ThemeColor.color_map["system_message"] = "#122E1E"
        if theme == "default":
            ThemeColor.color_map.pop("user_message", None)
            ThemeColor.color_map.pop("assistant_message", None)
            ThemeColor.color_map.pop("system_message", None)

def theme_color(name: str) -> str | None:
    return ThemeColor.get_theme_color(name)
