import logging

from ..models.signals import common_message_signal


gptui_logger = logging.getLogger("gptui_logger")


class GroupTalkControl:
    def __init__(self, app):
        self.app = app
        common_message_signal.connect(self.group_talk_user_message_send)

    def group_talk_user_message_send(self, sender, **kwargs):
        message = kwargs["message"]
        if message["flag"] == "group_talk_user_message_send":
            messages = message["content"]
            if isinstance(messages, list):
                for one_message in messages:
                    self.app.context_piece_to_chat_window(one_message, change_line=True, decorator_switch=True)
            else:
                self.app.context_piece_to_chat_window(messages, change_line=True, decorator_switch=True)
