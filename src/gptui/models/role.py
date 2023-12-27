from __future__ import annotations
import copy
import logging
from typing import TYPE_CHECKING, Iterable, Generator, cast

from agere.utils.llm_async_converters import LLMAsyncAdapter
from ai_care import AICare, AICareContext
from openai.types.chat import ChatCompletionMessageParam

from .context import BeadOpenaiContext, OpenaiContext
from .openai_error import OpenaiErrorHandler
from .openai_tokens_truncate import trim_excess_tokens
from .utils.openai_api import openai_api_client
from ..gptui_kernel.manager import ManagerInterface

if TYPE_CHECKING:
    from .jobs import GroupTalkManager


gptui_logger = logging.getLogger("gptui_logger")


class Role:
    def __init__(
        self,
        name: str,
        group_talk_manager: GroupTalkManager,
        manager: ManagerInterface,
        openai_context_parent: OpenaiContext
    ):
        """Role use the same openai parameters as in the parent conversation.
        """
        self.name = name
        self.context = BeadOpenaiContext(parameters=openai_context_parent.parameters)
        self.group_talk_manager = group_talk_manager
        self.manager = manager
        self.openai_api_client = openai_api_client(manager.dot_env_config_path)
        self.context.max_sending_tokens_num = openai_context_parent.max_sending_tokens_num
        self.openai_context_parent = openai_context_parent
        self.context.chat_context_saver = "inner"
        self.ai_care = AICare()
        self.ai_care.register_to_llm_method(self.to_llm_method)
        self.ai_care.register_to_user_method(self.to_user_method)
        self.ai_care.set_config(key="delay", value=60)

    def set_role_prompt(self, prompt: str):
        self.context.bead = [{"role": "system", "content": prompt}]
        self.context.insert_bead()
        self.ai_care.set_guide(
            prompt
            + "Plase maintain your role in the group chat, but if you want to say something, "
            + "there is no need to ask 'Can I speak?' first."
        )

    def chat(self, message: ChatCompletionMessageParam | list[ChatCompletionMessageParam]) -> Iterable:
        self.context.auto_insert_bead()
        if isinstance(message, dict):
            self.context.chat_context_append(message=message)
        else:
            for one_message in message:
                self.context.chat_context_append(message=one_message)
        self.context.parameters = self.openai_context_parent.parameters.copy()
        self.context.parameters["stream"] = True
        trim_messages = trim_excess_tokens(self.context, offset=0)
        try:
            response = self.openai_api_client.with_options(timeout=20.0).chat.completions.create(
                messages=trim_messages,
                **self.context.parameters,
            )
        except Exception as e:
            OpenaiErrorHandler().openai_error_handle(error=e, context=self.context, event_loop=True)
            raise e
        return response

    def to_llm_method(self, chat_context, to_llm_messages: list[AICareContext]) -> Generator[str, None, None]:
        messages_list = [
            {"role": "user", "name": "Aicarey", "content": message["content"]} if message["role"] == "ai_care"
            else {"role": "assistant", "content": message["content"]}
            for message in to_llm_messages
        ]
        context = copy.deepcopy(self.context)
        assert isinstance(context, BeadOpenaiContext)
        context.auto_insert_bead()
        for one_message in messages_list:
            one_message = cast(ChatCompletionMessageParam, one_message)
            context.chat_context_append(message=one_message)
        context.parameters = self.openai_context_parent.parameters.copy()
        context.parameters["stream"] = True
        trim_messages = trim_excess_tokens(context, offset=0)
        try:
            openai_response = self.openai_api_client.with_options(timeout=20.0).chat.completions.create(
                messages=trim_messages,
                **context.parameters,
            )
        except Exception as e:
            raise e
        else:
            def response_gen(response: Iterable):
                for chunk in response:
                    content = chunk.choices[0].delta.content
                    if content is None:
                        continue
                    yield content
            return response_gen(openai_response)

    def to_user_method(self, to_user_message: Generator[str, None, None]) -> None:
        with self.group_talk_manager._ai_care_rlock:
            if self.group_talk_manager.speaking is not None:
                return
            async_iterable = LLMAsyncAdapter().llm_to_async_iterable(to_user_message)
            self.group_talk_manager.ai_care_message_buffer.append({"name": f"{self.name}", "content": async_iterable})

    def ai_care_update(self):
        self.ai_care.chat_update(self.context)
