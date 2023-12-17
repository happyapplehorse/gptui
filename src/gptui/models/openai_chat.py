from __future__ import annotations
import logging
from abc import ABCMeta, abstractmethod
from typing import Literal

from agere.commander import Callback
from openai.types.chat import ChatCompletionMessageParam

from .blinker_wrapper import async_wrapper_without_loop, async_wrapper_with_loop, sync_wrapper
from .context import OpenaiContext
from .jobs import ResponseJob, GroupTalkManager
from .openai_error import OpenaiErrorHandler
from .openai_tokens_truncate import trim_excess_tokens
from .signals import notification_signal, chat_context_extend_for_sending_signal
from .utils.openai_api import openai_api_client
from .utils.tokens_num import tokens_num_for_functions_call
from ..gptui_kernel.manager import ManagerInterface


gptui_logger = logging.getLogger("gptui_logger")


class OpenaiChatInterface(metaclass=ABCMeta):
    @abstractmethod
    def chat_message_append(self, context: OpenaiContext, message: dict | list[dict]) -> None:
        ...
    
    @abstractmethod
    def chat_messages_extend(self, context: OpenaiContext, messages_list: list[dict]) -> None:
        ...
    
    @abstractmethod
    def chat_message_pop(self, context: OpenaiContext, pop_index: int = -1) -> dict:
        ...
    
    @abstractmethod
    def chat(self, context: OpenaiContext, message: dict | list[dict]) -> None:
        ...
    
    @abstractmethod
    def chat_stream(self, context: OpenaiContext, message: dict | list[dict]) -> None:
        ...


class OpenaiChat(OpenaiChatInterface):
    def __init__(self, manager: ManagerInterface):
        self.manager = manager
        self.openai_api_client = openai_api_client(manager.dot_env_config_path)

    def chat_message_append(self, context: OpenaiContext, message: dict | list[dict], tokens_num_update: bool = True) -> None:
        "Append chat message to the end of the chat_context of the context"
        if isinstance(message, dict):
            context.chat_context_append(message=message, tokens_num_update=tokens_num_update)
        else:
            for one_message in message:
                context.chat_context_append(message=one_message, tokens_num_update=tokens_num_update)

    def chat_messages_extend(self, context: OpenaiContext, messages_list: list[dict], tokens_num_update: bool = True) -> None:
        "Append a list of chat message to the end of the chat_context of the context"
        for message in messages_list:
            context.chat_context_append(message=message, tokens_num_update=tokens_num_update)
    
    def chat_message_pop(self, context: OpenaiContext, pop_index: int = -1) -> ChatCompletionMessageParam:
        "Pop a message from context"
        if context.chat_context is None:
            raise ValueError(f"Field 'chat_context' in {context.chat_context} has not been set.")
        return context.chat_context.pop(pop_index)

    def chat(self, context: OpenaiContext, message: dict | list[dict]) -> None:
        "Chat with openai"
        if isinstance(message, dict):
            messages_list = [message]
        else:
            messages_list = message

        if context.chat_context_saver_for_sending == "outer":
            chat_context_extend_for_sending_signal.send(
                self,
                _async_wrapper=async_wrapper_without_loop,
                message={
                    "content":{
                        "messages":messages_list,
                        "context":context,
                    },
                    "flag":"",
                }
            )
        else:
            self.chat_message_append(context=context, message=message)

        notification_signal.send(
            self,
            _async_wrapper=async_wrapper_without_loop,
            message={
                "content":{
                    "content":{"context":context},
                    "description":"Starting to send the original chat message from the user.",
                },
                "flag":"info",
            }
        )
        try:
            tools_para = {}
            if available_functions := self.manager.available_functions_meta:
                tools_para = {"tools": available_functions, "tool_choice": "auto"}
                response_mode = "function_call"
            else:
                response_mode = "no_function_call"
            
            offset_tokens_num = -tokens_num_for_functions_call(tools_para["tools"], model=context.parameters["model"])
            trim_messages = trim_excess_tokens(context, offset=offset_tokens_num)

            # Delete the tool reply messages at the beginning of the information list.
            # This is because if the information starts with a function reply message,
            # it indicates that the function call information has already been truncated.
            # The OpenAI API requires that function reply messages must be responses to function calls.
            # Therefore, if the function reply messages are not removed, it will result in an OpenAI API error.
            while trim_messages and trim_messages[0].get("role") == "tool":
                trim_messages.pop(0)

            response = self.openai_api_client.with_options(timeout=20.0).chat.completions.create(
                messages=trim_messages,
                **tools_para,
                **context.parameters,
            )
        except Exception as e:
            notification_signal.send(
                self,
                _async_wrapper=async_wrapper_without_loop,
                message={
                    "content":{
                        "content":{"error":e, "context":context},
                        "description":"An error occurred in communication with OpenAI initiated by user."
                    },
                    "flag":"info"
                }
            )
            OpenaiErrorHandler().openai_error_handle(error=e, context=context, event_loop=False)
            return

        response_stream_format = response_to_stream_format(mode=response_mode, response=response)
        
        callback = Callback(
            at_job_start=[
                {
                    "function": notification_signal.send,
                    "params": {
                        "args": (self,),
                        "kwargs": {
                            "_async_wrapper": async_wrapper_with_loop,
                            "message":{
                                "content":{
                                    "content":{"status": True, "context": context},
                                    "description":"Job status changed",
                                },
                                "flag":"info",
                            },
                        },
                    },
                },
            ],
            at_job_end=[
                {
                    "function": notification_signal.send_async,
                    "params": {
                        "args": (self,),
                        "kwargs": {
                            "_sync_wrapper": sync_wrapper,
                            "message":{
                                "content":{
                                    "content":{"status": False, "context": context},
                                    "description":"Job status changed",
                                },
                                "flag":"info",
                            },
                        },
                    },
                },
            ],
        )

        at_receiving_start = [
            {
                "function": notification_signal.send,
                "params": {
                    "args": (self,),
                    "kwargs": {
                        "_async_wrapper": async_wrapper_with_loop,
                        "message":{
                            "content":{
                                "content":{"context": context},
                                "description":"Starting to receive the original response message to the user",
                            },
                            "flag":"info",
                        },
                    },
                },
            },
        ]

        job = ResponseJob(
            manager=self.manager,
            response=response_stream_format,
            context=context,
            callback=callback,
            at_receiving_start=at_receiving_start,
        )
        self.manager.gk_kernel.commander.put_job_threadsafe(job)
    
    def chat_stream(self, context: OpenaiContext, message: dict | list[dict]) -> None:
        "stream version of chat function with openai"
        if isinstance(message, dict):
            messages_list = [message]
        else:
            messages_list = message

        if context.chat_context_saver_for_sending == "outer":
            chat_context_extend_for_sending_signal.send(
                self,
                _async_wrapper=async_wrapper_without_loop,
                message={
                    "content":{
                        "messages":messages_list,
                        "context":context,
                    },
                    "flag":"",
                }
            )
        else:
            self.chat_message_append(context=context, message=message)

        notification_signal.send(
            self,
            _async_wrapper=async_wrapper_without_loop,
            message={
                "content":{
                    "content":{"context":context},
                    "description":"Starting to send the original chat message from the user.",
                },
                "flag":"info",
            }
        )
        try:
            tools_para = {}
            if available_functions := self.manager.available_functions_meta:
                tools_para = {"tools": available_functions, "tool_choice": "auto"}
            
            offset_tokens_num = -tokens_num_for_functions_call(tools_para["tools"], model=context.parameters["model"])
            trim_messages = trim_excess_tokens(context, offset=offset_tokens_num)

            # Delete the tool reply messages at the beginning of the information list.
            # This is because if the information starts with a function reply message,
            # it indicates that the function call information has already been truncated.
            # The OpenAI API requires that function reply messages must be responses to function calls.
            # Therefore, if the function reply messages are not removed, it will result in an OpenAI API error.
            while trim_messages and trim_messages[0].get("role") == "tool":
                trim_messages.pop(0)

            response = self.openai_api_client.with_options(timeout=20.0).chat.completions.create(
                messages = trim_messages,
                **tools_para,
                **context.parameters,
                )
        except Exception as e:
            notification_signal.send(
                self,
                _async_wrapper=async_wrapper_without_loop,
                message={
                    "content":{
                        "content":{"error":e, "context":context},
                        "description":"An error occurred in communication with OpenAI initiated by user."
                    },
                    "flag":"info"
                }
            )
            OpenaiErrorHandler().openai_error_handle(error=e, context=context, event_loop=False)
            return
        
        callback = Callback(
            at_job_start=[
                {
                    "function": notification_signal.send,
                    "params": {
                        "args": (self,),
                        "kwargs": {
                            "_async_wrapper": async_wrapper_with_loop,
                            "message":{
                                "content":{
                                    "content":{"status": True, "context": context},
                                    "description":"Job status changed",
                                },
                                "flag":"info",
                            },
                        },
                    },
                },
            ],
            at_job_end=[
                {
                    "function": notification_signal.send_async,
                    "params": {
                        "args": (self,),
                        "kwargs": {
                            "_sync_wrapper": sync_wrapper,
                            "message":{
                                "content":{
                                    "content":{"status": False, "context": context},
                                    "description":"Job status changed",
                                },
                                "flag":"info",
                            },
                        },
                    },
                },
            ],
        )
        
        at_receiving_start = [
            {
                "function": notification_signal.send,
                "params": {
                    "args": (self,),
                    "kwargs": {
                        "_async_wrapper": async_wrapper_with_loop,
                        "message":{
                            "content":{
                                "content":{"context": context},
                                "description":"Starting to receive the original response message to the user",
                            },
                            "flag":"info",
                        },
                    },
                },
            },
        ]

        job = ResponseJob(
            manager=self.manager,
            response=response,
            context=context,
            callback=callback,
            at_receiving_start=at_receiving_start,
        )
        self.manager.gk_kernel.commander.put_job_threadsafe(job)


def response_to_stream_format(mode: Literal["no_function_call", "function_call"], response) -> list:
    if mode == "no_function_call":
        reply_content = response.choices[0].message.content
        finish_reason = response.choices[0].finish_reason
        result = [{"choices":[{"delta":{"content":""}, "finish_reason":"null"}]}, 
                                     {"choices":[{"delta":{"content":reply_content}, "finish_reason":"null"}]},
                                     {"choices":[{"delta":{}, "finish_reason":finish_reason}]}]
    elif mode == "function_call":
        reply_message = response.choices[0].message
        reply_content = reply_message.get("content")
        finish_reason = response.choices[0].finish_reason
        reply_function_call = reply_message.get("function_call")
        if reply_function_call is not None:
            name = reply_function_call.get("name")
            arguments = reply_function_call.get("arguments")
            result = [{"choices":[{"delta":{"content":None, "function_call":{"name":name}}, "finish_reason":"null"}]}, 
                                         {"choices":[{"delta":{"function_call": {"arguments":arguments}}, "finish_reason":"null"}]},
                                         {"choices":[{"delta":{}, "finish_reason":finish_reason}]}]
        else:
            result = [{"choices":[{"delta":{"content":""}, "finish_reason":"null"}]}, 
                                         {"choices":[{"delta":{"content":reply_content}, "finish_reason":"null"}]},
                                         {"choices":[{"delta":{}, "finish_reason":finish_reason}]}]
    return result


class OpenAIGroupTalk:
    def __init__(self, manager: ManagerInterface):
        self.manager = manager
        self.openai_api_client = openai_api_client(manager.dot_env_config_path)

    def talk_stream(self, group_talk_manager: GroupTalkManager, message_content: str) -> None:
        if group_talk_manager.state != "ACTIVE":
            group_talk_manager.speaking = None
            group_talk_manager.running = True
            group_talk_manager.user_talk_buffer.append(message_content)
            self.manager.gk_kernel.commander.put_job_threadsafe(group_talk_manager)
        else:
            group_talk_manager.user_talk_buffer.append(message_content)
