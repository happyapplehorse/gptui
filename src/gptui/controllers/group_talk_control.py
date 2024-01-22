import logging

from ..models.signals import common_message_signal
from ..views.mywidgets import ChatBoxMessage


gptui_logger = logging.getLogger("gptui_logger")


class GroupTalkControl:
    def __init__(self, app):
        self.app = app
        common_message_signal.connect(self.group_talk_user_message_send)

    def group_talk_user_message_send(self, sender, **kwargs):
        message = kwargs["message"]
        if message["flag"] == "group_talk_user_message_send":
            messages = message["content"]["messages"]
            group_talk_manager = message["content"]["group_talk_manager"]
            group_talk_manager_id = group_talk_manager.group_talk_manager_id
            chat_window_id = 'lxt' + str(group_talk_manager_id)
            chat_window = self.app.main_screen.query_one("#chat_region").get_child_by_id(chat_window_id)
            if isinstance(messages, list):
                for one_message in messages:
                    chat_box = ChatBoxMessage.make_message_box(message=one_message["content"], role="user", name=one_message["name"])
                    self.app.call_from_thread(chat_window.add_box, chat_box)
            else:
                chat_box = ChatBoxMessage.make_message_box(message=message["content"], role="user", name=message["name"])
                self.app.call_from_thread(chat_window.add_box, chat_box)
