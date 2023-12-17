import logging

from .dash_board_control import DashBoard
from ..models.signals import chat_context_extend_signal, chat_context_extend_for_sending_signal
from ..views.common_message import CommonMessage

gptui_logger = logging.getLogger("gptui_logger")


class ChatContextControl:
    def __init__(self, app):
        self.app = app
        self.dash_board = DashBoard(app)
        self.chat_context_to_vectorize_buffer = {}
        chat_context_extend_signal.connect(self.chat_context_extend)
        chat_context_extend_for_sending_signal.connect(self.chat_context_extend_for_sending)

    def chat_context_extend(self, sender, **kwargs):
        signal_message = kwargs["message"]
        signal_content = signal_message["content"]
        messages = signal_content["messages"]
        context = signal_content["context"]
        openai_chat = self.app.openai.openai_chat
        
        openai_chat.chat_messages_extend(messages_list=messages, context=context)
        buffer_messages = self.chat_context_to_vectorize_buffer.get(context.id, [])
        buffer_messages.extend(messages)
        self.chat_context_to_vectorize_buffer[context.id] = buffer_messages
        
        _, whether_insert = self.app.openai.auto_bead_insert(context.id)
        
        if whether_insert is False:
            # dashboard display
            model = context.parameters["model"]
            self.dash_board.dash_board_display(tokens_num_window=self.app.get_tokens_window(model))
    
    def chat_context_extend_for_sending(self, sender, **kwargs):
        signal_message = kwargs["message"]
        signal_content = signal_message["content"]
        messages = signal_content["messages"]
        context = signal_content["context"]
        openai_chat = self.app.openai.openai_chat
        
        openai_chat.chat_messages_extend(messages_list=messages, context=context)
        buffer_messages = self.chat_context_to_vectorize_buffer.get(context.id, [])
        buffer_messages.extend(messages)
        self.chat_context_to_vectorize_buffer[context.id] = buffer_messages
        
        self.app.openai.auto_bead_insert(context.id)

    async def chat_context_vectorize(self):
        while self.chat_context_to_vectorize_buffer:
            id, messages_list = self.chat_context_to_vectorize_buffer.popitem()
            self.app.post_message(
                CommonMessage(
                    message_name="vector_memory_write",
                    message_content={
                        "messages_list": messages_list,
                        "context_id": id,
                    }
                )
            )
