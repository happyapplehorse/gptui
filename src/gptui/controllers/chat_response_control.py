import logging
import threading

from ..utils.my_text import MyText as Text
from ..utils.my_text import MyLines as Lines
from ..models.signals import response_to_user_message_stream_signal, response_auxiliary_message_signal


gptui_logger = logging.getLogger("gptui_logger")


class ChatResponse:
    def __init__(self, app):
        self.app = app
        self.chat_region = app.main_screen.query_one("#chat_region")
        self.app_chat_tabs = app.main_screen.query_one("#chat_tabs")
        self.buffer = {}
        self.tab_not_switching = threading.Event()
        self.tab_not_switching.set()
        response_to_user_message_stream_signal.connect(self.handle_response)
        response_auxiliary_message_signal.connect(self.handle_group_talk_response)
    
    def delete_buffer_id(self, id: int) -> None:
        self.buffer.pop(id, None)

    def handle_response(self, sender, **kwargs):
        message = kwargs["message"]
        self.stream_display(message)

    def stream_display(self, message: dict, stream: bool = True, copy_code: bool = False) -> None:
        """Display the chat response in TUI"""
        # If the tab is in the process of switching, wait for the chat history to finish loadind
        # before displaying the newly generating chat content.    
        self.tab_not_switching.wait(2)
        context_id = message["content"]["context_id"]
        tab_id = int(self.app_chat_tabs.active[3:])
        if context_id not in self.buffer:
            self.buffer[context_id] = {
                "chat_stream_content": {"role": "assistant", "content": ""},
                "decorate_chat_stream_content_lines": Lines(),
                "last_tab_id": tab_id,
            }
        buffer_context = self.buffer[context_id]
        chat_stream_content = buffer_context["chat_stream_content"]
        char = message["content"]["content"]
        if message["flag"] == "content":
            # This condition being met indicates that the currently generated content corresponds with the active tab window,
            # and it is not the first time being displayed.
            if context_id == tab_id == buffer_context["last_tab_id"]:
                length = len(buffer_context["decorate_chat_stream_content_lines"])
                self.chat_region.right_pop_lines(length, refresh=False)
            chat_stream_content["content"] += char
            if context_id == tab_id:
                buffer_context["decorate_chat_stream_content_lines"] = self.app.decorator(chat_stream_content, stream, copy_code)
                self.chat_region.write_lines(buffer_context["decorate_chat_stream_content_lines"])
        elif message["flag"] == "end":
            if context_id == tab_id:
                self.stream_display(message={"content": {"content": "", "context_id": context_id}, "flag": "content"}, stream=False, copy_code=True)
                self.chat_region.write_lines([Text()])
            chat_stream_content["content"] = ""
            buffer_context["decorate_chat_stream_content_lines"] = Lines()
        buffer_context["last_tab_id"] = tab_id

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
        tab_id = int(self.app_chat_tabs.active[3:])
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
