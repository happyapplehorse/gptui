import logging

from ..utils.my_text import MyText as Text
from ..utils.my_text import MyLines as Lines
from ..models.signals import response_to_user_message_stream_signal


gptui_logger = logging.getLogger("gptui_logger")


class ChatResponse:
    def __init__(self, app):
        self.app = app
        self.chat_stream_content = {"role":"assistant", "content":""}
        self.decorate_chat_stream_content_lines = Lines()
        response_to_user_message_stream_signal.connect(self.handle_response)
    
    def handle_response(self, sender, **kwargs):
        message = kwargs["message"]
        self.stream_display(message)

    def stream_display(self, message: dict, stream: bool = True, copy_code: bool = False) -> None:
        """Display the chat response in TUI"""
        app = self.app
        chat_region = app.query_one("#chat_region")
        char = message["content"]
        if message["flag"] == "content":
            length = len(self.decorate_chat_stream_content_lines)
            chat_region.right_pop_lines(length, refresh=False)
            self.chat_stream_content["content"] += char
            self.decorate_chat_stream_content_lines = self.app.decorator(self.chat_stream_content, stream, copy_code)
            chat_region.write_lines(self.decorate_chat_stream_content_lines)
        elif message["flag"] == "end":
            self.stream_display(message={"content":"", "flag":"content"}, stream=False, copy_code=True)
            chat_region.write_lines([Text()])
            self.chat_stream_content = {"role":"assistant", "content":""}
            self.decorate_chat_stream_content_lines = Lines()
