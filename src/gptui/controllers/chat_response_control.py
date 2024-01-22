import logging
import threading

from textual.css.query import NoMatches

from ..utils.my_text import MyText as Text
from ..utils.my_text import MyLines as Lines
from ..models.signals import response_to_user_message_stream_signal, response_auxiliary_message_signal
from ..views.mywidgets import ChatBoxMessage


gptui_logger = logging.getLogger("gptui_logger")


class ChatResponse:
    def __init__(self, app):
        self.app = app
        self.chat_region = app.main_screen.query_one("#chat_region")
        self.app_chat_tabs = app.main_screen.query_one("#chat_tabs")
        self.tab_not_switching = threading.Event()
        self.tab_not_switching.set()
        response_to_user_message_stream_signal.connect(self.handle_response)
        response_auxiliary_message_signal.connect(self.handle_group_talk_response)
    
    def handle_response(self, sender, **kwargs):
        message = kwargs["message"]
        self.stream_display(message)

    def stream_display(self, message: dict) -> None:
        """Display the chat response in TUI"""
        context_id = message["content"]["context_id"]
        try:
            chat_window = self.chat_region.get_child_by_id('lqt' + str(context_id))
        except NoMatches:
            return
        if message["flag"] == "content":
            char = message["content"]["content"]
            if chat_window.current_box is None:
                chat_box = ChatBoxMessage.make_message_box(message=char, role="assistant")
                self.app.call_from_thread(chat_window.add_box, chat_box)
                chat_window.current_box = chat_box
            else:
                self.app.call_from_thread(chat_window.current_box.content_append, char)
        elif message["flag"] == "end":
            chat_window.current_box = None
        else:
            assert False

    def handle_group_talk_response(self, sender, **kwargs):
        message = kwargs["message"]
        message_content = message["content"]
        flag = message["flag"]
        if flag == "group_talk_response":
            self.group_talk_stream_display(message=message_content)
    
    def group_talk_stream_display(self, message: dict, stream: bool = True, copy_code: bool = False) -> None:
        """Display the group talk response in TUI"""
        message_dict = message["content"]
        group_talk_manager_id = message_dict["group_talk_manager_id"]
        if (active_tab := self.app_chat_tabs.active_tab) is not None:
            tab_id = int(active_tab.id[3:])
        else:
            tab_id = 0
        if group_talk_manager_id not in self.buffer:
            self.buffer[group_talk_manager_id] = {
                "group_talk_chat_stream_content": {"role": "assistant", "name": "", "content": ""},
                "group_talk_decorate_chat_stream_content_lines": Lines(),
                "last_tab_id": tab_id,
            }
        buffer_context = self.buffer[group_talk_manager_id]
        group_talk_chat_stream_content = buffer_context["group_talk_chat_stream_content"]
        char = message_dict["content"]
        group_talk_chat_stream_content["name"] = message_dict["name"]
        if message["flag"] == "content":
            # This condition being met indicates that the currently generated content corresponds with the active tab window,
            # and it is not the first time being displayed.
            if group_talk_manager_id == tab_id == buffer_context["last_tab_id"]:
                length = len(buffer_context["group_talk_decorate_chat_stream_content_lines"])
                self.chat_region.right_pop_lines(length, refresh=False)
            group_talk_chat_stream_content["content"] += char
            buffer_context["group_talk_decorate_chat_stream_content_lines"] = self.app.decorator(group_talk_chat_stream_content, stream, copy_code)
            if group_talk_manager_id == tab_id:
                self.chat_region.write_lines(buffer_context["group_talk_decorate_chat_stream_content_lines"])
        elif message["flag"] == "end":
            if group_talk_manager_id == tab_id:
                self.group_talk_stream_display(message={"content": {"role": "assistant", "name": message_dict["name"], "content": "", "group_talk_manager_id": group_talk_manager_id}, "flag": "content"}, stream=False, copy_code=True)
                self.chat_region.write_lines([Text()])
            group_talk_chat_stream_content["content"] = ""
            buffer_context["group_talk_decorate_chat_stream_content_lines"] = Lines()
        buffer_context["last_tab_id"] = tab_id
