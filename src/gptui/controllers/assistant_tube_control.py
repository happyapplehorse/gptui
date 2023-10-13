import logging

from ..models.signals import response_auxiliary_message_signal


gptui_logger = logging.getLogger("gptui_logger")


class AssistantTube:
    def __init__(self, app):
        self.app = app
        response_auxiliary_message_signal.connect(self.tube_display)

    def tube_display(self, sender, **kwargs):
        message = kwargs["message"]
        content = message["content"]
        flag = message["flag"]
        if flag == "function_call":
            self.app.context_piece_to_assistant_tube(content)
        elif flag == "function_response":
            self.app.context_piece_to_assistant_tube(content)
