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

    def handle_group_talk_response(self, sender, **kwargs) -> None:
        message = kwargs["message"]
        message_content = message["content"]
        flag = message["flag"]
        if flag == "group_talk_response":
            self.group_talk_stream_display(message=message_content)
    
    def group_talk_stream_display(self, message: dict) -> None:
        """Display the group talk response in TUI"""
        message_dict = message["content"]
        group_talk_manager_id = message_dict["group_talk_manager_id"]
        try:
            chat_window = self.chat_region.get_child_by_id('lxt' + str(group_talk_manager_id))
        except NoMatches:
            return
        if message["flag"] == "content":
            char = message_dict["content"]
            if chat_window.current_box is None:
                chat_box = ChatBoxMessage.make_message_box(message=char, role="assistant", name=message_dict["name"])
                self.app.call_from_thread(chat_window.add_box, chat_box)
                chat_window.current_box = chat_box
            else:
                self.app.call_from_thread(chat_window.current_box.content_append, char)
        elif message["flag"] == "end":
            chat_window.current_box = None
        else:
            assert False
