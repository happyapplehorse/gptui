import logging
from typing import Iterable

from .context import OpenaiContext
from .openai_error import OpenaiErrorHandler
from .openai_tokens_truncate import trim_excess_tokens
from .utils.openai_api import openai_api
from ..gptui_kernel.manager import ManagerInterface


gptui_logger = logging.getLogger("gptui_logger")


class Role:
    def __init__(self, name: str, system_message: str, manager: ManagerInterface, openai_context_parent: OpenaiContext):
        """Role use the same openai parameters as in the parent conversation."""
        self.name = name
        self.context = OpenaiContext()
        self.manager = manager
        self.openai_api = openai_api(manager.dot_env_config_path)
        self.context.chat_context_append({"role": "system", "content": system_message})
        self.context.max_sending_tokens_num = openai_context_parent.max_sending_tokens_num
        self.openai_context_parent = openai_context_parent
        self.context.chat_context_saver = "inner"

    def chat(self, message: dict | list[dict]) -> Iterable:
        if isinstance(message, dict):
            self.context.chat_context_append(message=message)
        else:
            for one_message in message:
                self.context.chat_context_append(message=one_message)
        self.context.parameters = self.openai_context_parent.parameters.copy()
        self.context.parameters["stream"] = True
        trim_messages = trim_excess_tokens(self.context, offset=0)
        try:
            response = self.openai_api.ChatCompletion.create(
                messages=trim_messages,
                **self.context.parameters,
            )
        except Exception as e:
            OpenaiErrorHandler().openai_error_handle(error=e, context=self.context, event_loop=True)
            raise e
        return response
