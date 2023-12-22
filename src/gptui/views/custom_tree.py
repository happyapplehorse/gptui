import os
from typing import Generic

from rich.style import Style
from textual.widgets import Tree, DirectoryTree
from textual.widgets._directory_tree import DirEntry
from textual.widgets._tree import TreeNode, TreeDataType, TOGGLE_STYLE

from .theme import ThemeColor
from .theme import theme_color as tc
from ..utils.my_text import MyText as Text

class MyDirectoryTree(DirectoryTree):
    def __init__(self, root_path: str, *args, **kwargs):
        self.root_path = root_path
        self.file_path_now = self.root_path
        super().__init__(*args, **kwargs)

    def on_directory_tree_file_selected(self, event) -> None:
        self.file_path_now = event.path

    def on_directory_tree_directory_selected(self, event) -> None:
        self.file_path_now = event.path
        if str(event.path) == self.root_path:
            self.reload()
    
    def render_label(
        self, node: TreeNode[DirEntry], base_style: Style, style: Style
    ) -> Text:
        """Render a label for the given node.

        Args:
            node: A tree node.
            base_style: The base style of the widget.
            style: The additional style for the label.

        Returns:
            A Rich Text object containing the label.
        """
        is_monochrome_theme = True if ThemeColor._theme == "monochrome" else False

        node_label = node._label.copy()
        node_label.stylize(style)
        color_style = Style(color = tc("green") or "green")

        if node._allow_expand:
            if is_monochrome_theme:
                prefix = ("➘ " if node.is_expanded else "➩ ", base_style + color_style + TOGGLE_STYLE)
            else:
                prefix = ("📂 " if node.is_expanded else "📁 ", base_style + TOGGLE_STYLE)
            node_label.stylize_before(
                self.get_component_rich_style("directory-tree--folder", partial=True)
            )
        else:
            if is_monochrome_theme:
                prefix = ("◉ ", base_style + color_style)
            else:
                prefix = (
                    "📄 ",
                    base_style,
                )
            node_label.stylize_before(
                self.get_component_rich_style("directory-tree--file", partial=True),
            )
            node_label.highlight_regex(
                r"\..+$",
                self.get_component_rich_style(
                    "directory-tree--extension", partial=True
                ),
            )

        if node_label.plain.startswith("."):
            node_label.stylize_before(
                self.get_component_rich_style("directory-tree--hidden")
            )

        text = Text.assemble(prefix, node_label)
        return text


class ConversationTree(Tree, Generic[TreeDataType]):
    def __init__(self, conversation_path: str, *args, **kwargs):
        self.conversation_path = conversation_path
        super().__init__(*args, **kwargs)
        
    @property
    def file_path_now(self):
        if self.cursor_node:
            return self.cursor_node.data
        else:
            return None

    def on_tree_node_selected(self, event):
        if event.node is self.root:
            self.conversation_refresh()
    
    def conversation_refresh(self):
        self.clear()
        self.root.expand()
        conversation_path = self.conversation_path
        try:
            for filename in os.listdir(conversation_path):
                if filename.endswith(".json") and (filename != "_conversations_cache.json"):
                    self.root.add_leaf(f"{filename}", data=os.path.join(conversation_path, filename))
        except FileNotFoundError:
            pass

    def render_label(
        self, node: TreeNode[TreeDataType], base_style: Style, style: Style
    ) -> Text:
        """Render a label for the given node. Override this to modify how labels are rendered.

        Args:
            node: A tree node.
            base_style: The base style of the widget.
            style: The additional style for the label.

        Returns:
            A Rich Text object containing the label.
        """
        node_label = node._label.copy()
        node_label.stylize(style)

        if node._allow_expand:
            if ThemeColor._theme == "monochrome":
                color_style = Style(color = tc("green") or "green")
                prefix = ("▼ " if node.is_expanded else "▶ ", base_style + color_style + TOGGLE_STYLE)
            else:
                prefix = (
                    "▼ " if node.is_expanded else "▶ ",
                    base_style + TOGGLE_STYLE,
                )
        else:
            prefix = ("", base_style)
        
        text = Text.assemble(prefix, node_label)
        return text
