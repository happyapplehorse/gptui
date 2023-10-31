import asyncio
import copy
import json
import logging
import random
from dataclasses import asdict
from typing import Iterable, AsyncIterable

from .blinker_wrapper import sync_wrapper, async_wrapper_with_loop
from .context import OpenaiContext
from .signals import (
    chat_context_extend_signal,
    common_message_signal,
    notification_signal,
    response_auxiliary_message_signal,
    response_to_user_message_stream_signal,
    response_to_user_message_sentence_stream_signal,
)
from .openai_chat_inner_service import chat_service_for_inner
from .openai_error import OpenaiErrorHandler
from .utils.openai_api import openai_api
from ..gptui_kernel.dispatcher import(
    async_iterable_from_gpt,
    async_dispatcher_function_call,
)
from ..gptui_kernel.manager import ManagerInterface
from ..gptui_kernel.kernel import BasicJob, handler, Callback
from ..gptui_kernel.dispatcher import async_iterable_from_gpt


gptui_logger = logging.getLogger("gptui_logger")


class ResponseHandler:
    """A handler to handle response from LLM."""
    def __init__(self, manager: ManagerInterface, context: OpenaiContext):
        self.manager = manager
        self.context = context

    @handler
    async def handle_response(self, self_handler, response, callback):
        """handler that handle response from LLM"""
        commander = self_handler.commander
        make_role_generator = await async_dispatcher_function_call(
            source=async_iterable_from_gpt(
                response=response,
                callback=callback,
            ),
            task_keeper=commander.task_keeper,
        )
        to_user_gen = make_role_generator("to_user")
        function_call_gen = make_role_generator("function_call")
        response_to_user_job = BasicJob(OpenaiHandler(self.manager, self.context).user_handler(user_gen=to_user_gen))
        await self_handler.put_job(job=response_to_user_job)
        function_call_job = BasicJob(OpenaiHandler(self.manager, self.context).function_call_handler(function_call_gen=function_call_gen))
        await self_handler.put_job(job=function_call_job)


class OpenaiHandler:
    """A handler for processing OpenAI responses"""

    def __init__(self, manager: ManagerInterface, context: OpenaiContext):
        self.manager = manager
        self.context = context
        self.chat_context_saver = context.chat_context_saver
        self.openai_api = openai_api(manager.dot_env_config_path)

    @handler
    async def user_handler(self, self_handler, user_gen) -> None:
        """Handling the part of the message sent to the user by LLM
        args:
            user_gen: a iterable object including the message to user
        actions:
            blinker_signal:
                response_to_user_message_stream_signal: send the to_user part of chat message, which usually should be displayed.
                response_to_user_message_sentence_stream: send the voice stream divided by common punctuation marks.
        """
        empty_status = None
        collected_messages = ""
        voice_buffer = ""
        
        async for char in user_gen:
            empty_status = False
            collected_messages += char
            await response_to_user_message_stream_signal.send_async(
                self,
                _sync_wrapper=sync_wrapper,
                message={"content": {"content": char, "context_id": self.context.id}, "flag": "content"},
            )
            
            # Send voice signal
            if response_to_user_message_sentence_stream_signal.receivers:
                voice_buffer += char
                if char.startswith((".","!","?",";",":","。","！","？","；","：","\n")):
                    await response_to_user_message_sentence_stream_signal.send_async(
                        self,
                        _sync_wrapper=sync_wrapper,
                        message={"content": voice_buffer, "flag": "content"},
                    )
                    voice_buffer = ""
        
        if empty_status is None:
            return
        if voice_buffer:
            await response_to_user_message_sentence_stream_signal.send_async(
                self,
                _sync_wrapper=sync_wrapper,
                message={"content": voice_buffer, "flag": "content"},
            )
            voice_buffer = ""

        await response_to_user_message_stream_signal.send_async(
            self,
            _sync_wrapper=sync_wrapper,
            message={"content": {"content": "", "context_id": self.context.id}, "flag": "end"},
        )
        
        # save response to context
        if self.chat_context_saver == "outer":
            await chat_context_extend_signal.send_async(
                self,
                _sync_wrapper=sync_wrapper,
                message={
                    "content":{
                        "messages": [{"role": "assistant", "content": collected_messages}],
                        "context": self.context,
                    },
                    "flag": "",
                }
            )
        else:
            self.context.chat_context_append({"role": "assistant", "content": collected_messages})
        # Send voice end signal
        if response_to_user_message_sentence_stream_signal.receivers:
            await response_to_user_message_sentence_stream_signal.send_async(self, _sync_wrapper=sync_wrapper, message={"content":"", "flag":"end"})
    
    @handler
    async def function_call_handler(self, self_handler, function_call_gen) -> None:
        message_list = []
        async for chunk in function_call_gen:
            message_list.append(chunk)
        message = ''.join(message_list)
        if not message:
            return
        function_dict = {}
        try:
            function_dict = json.loads(message)
        except json.JSONDecodeError as e:
            gptui_logger.error(e)
        if function_dict.get("name"):
            # call the function
            function_name = function_dict["name"]
            function_to_call = self.manager.available_functions_link[function_name]
            function_args = function_dict["arguments"]
            
            await notification_signal.send_async(
                self,
                _sync_wrapper=sync_wrapper,
                message={
                    "content":{
                        "content": "Function calling: " + function_name + " ... ",
                        "description": "raw",
                    },
                    "flag": "info",
                }
            )

            context = self.manager.gk_kernel.context_render(args=function_args, function=function_to_call)
            
            # dose insert context
            if context.variables.get("openai_context") == (True, "AUTO"):
                openai_context_deepcopy = copy.deepcopy(self.context)
                openai_context_deepcopy.plugins = [repr(plugin) for plugin in openai_context_deepcopy.plugins]
                context["openai_context"] = json.dumps(asdict(openai_context_deepcopy))

            function_call_display_str = f"{function_name}({', '.join(f'{k}={v}' for k, v in function_args.items())})"
            await response_auxiliary_message_signal.send_async(
                self,
                _sync_wrapper=sync_wrapper,
                message={
                    "content":{"role": "gpt", "content": f"Function call: {function_call_display_str}"},
                    "flag":"function_call",
                }
            )
            gptui_logger.info("Function call: " + function_call_display_str)
            function_response_context = await function_to_call.invoke_async(context=context)
            function_response = str(function_response_context)
            
            # send the function response to GPT
            message = [
                {
                    "role": "function",
                    "name": function_name,
                    "content": function_response,
                }
            ]
            functions = self.manager.available_functions_meta
            await notification_signal.send_async(
                self,
                _sync_wrapper=sync_wrapper,
                message={
                    "content": {
                        "content": "Send function call result, waiting for response ...",
                        "description": "raw",
                    },
                    "flag": "info",
                }
            )
            if functions:
                paras = {"messages_list": message, "context": self.context, "openai_api": self.openai_api, "functions": functions, "function_call": "auto"}
            else:
                paras = {"messages_list": message, "context": self.context, "openai_api": self.openai_api}
            try:
                await response_auxiliary_message_signal.send_async(self, _sync_wrapper=sync_wrapper, message={"content":message[0], "flag":"function_response"})
                # add response to context
                if self.chat_context_saver == "outer":
                    await chat_context_extend_signal.send_async(
                        self,
                        _sync_wrapper=sync_wrapper,
                        message={
                            "content":{
                                "messages": [
                                    {
                                        "role": "system",
                                        "content": (
                                            f"<log />Assistant called function: {function_call_display_str}\n"
                                            "This is an automatically logged message to remind you of your function call history.\n"
                                        )
                                    },
                                ],
                                "context": self.context
                            },
                            "flag": "",
                        }
                    )
                else:
                    self.context.chat_context_append(
                        {
                            "role": "system",
                            "content": (
                                f"<log />Assistant called function: {function_call_display_str}\n"
                                "This is an automatically logged message to remind you of your function call history.\n"
                            )
                        }
                    )
                response = await asyncio.to_thread(chat_service_for_inner, **paras)
            except Exception as e:
                OpenaiErrorHandler().openai_error_handle(error=e, context=self.context)
                raise e
            if self.chat_context_saver == "outer":
                await chat_context_extend_signal.send_async(
                    self,
                    _sync_wrapper=sync_wrapper,
                    message={
                        "content": {
                            "messages": message,
                            "context": self.context
                        },
                        "flag":"function_response"}
                )
            else:
                self.context.chat_context_append(message[0])
            #self.context_record(message)
            ResponseJob = self.manager.get_job("ResponseJob")
            callback = Callback(
                at_receiving_start=[
                    {
                        "function": notification_signal.send,
                        "params": {
                            "args": (self,),
                            "kwargs": {
                                "_async_wrapper": async_wrapper_with_loop,
                                "message":{
                                    "content":{
                                        "content": "Starting to receive response messages for function calls.",
                                        "description": "raw",
                                    },
                                    "flag":"info",
                                },
                            },
                        },
                    },
                ],
            )
            await self_handler.put_job(ResponseJob(response=response, manager=self.manager, context=self.context, callback=callback))


class GroupTalkHandler:
    @handler
    async def handle_response(self, self_handler, response_dict: dict[str, Iterable]):
        items = list(response_dict.items())
        # Randomly shuffle the order to give each role an equal opportunity to speak.
        random.shuffle(items)
        for role_name, response in items:
            self_handler.call_handler(self.parse_stream_response(role_name, response))

    @handler
    async def wait_for_termination(self, self_handler, group_talk_manager):
        while True:
            await asyncio.sleep(1)
            # If no one is speaking, check if the user is speaking.
            if group_talk_manager.speaking is None:
                messages = [{"role": "user", "name": "host", "content": message} for message in group_talk_manager.user_talk_buffer]
                if messages:
                    common_message_signal.send(
                        self,
                        _async_wrapper=async_wrapper_with_loop,
                        message={
                            "content": messages,
                            "flag": "group_talk_user_message_send",
                        },
                    )
                    response_dict = {}
                    items = list(group_talk_manager.roles.items())
                    # Randomly shuffle the order to give each role an equal opportunity to speak.
                    random.shuffle(items)
                    for role_name, role in items:
                        response_dict[role_name] = role.chat(message=messages)
                    GroupTalkHandler = group_talk_manager.manager.get_handler("GroupTalkHandler")
                    # Because at any given moment only one role can speak, it is safe when multiple dialogue tasks are running in parallel;
                    # there will be no inconsistency in the role's chat history.
                    self_handler.call_handler(GroupTalkHandler().handle_response(response_dict))
                    group_talk_manager.user_talk_buffer = []
            if not group_talk_manager.running:
                await group_talk_manager.close_task_node()
                break

    @handler
    async def parse_stream_response(self, self_handler, role_name, stream_response):
        async_stream_response = async_iterable_from_gpt(stream_response)
        talk_manager = self_handler.ancestor_chain[-2]
        if not talk_manager.running:
            return
        full_response_content = await self.stream_response_result(async_stream_response=async_stream_response)
        if "Can I speak" in full_response_content:
            role = talk_manager.roles[role_name]
            if talk_manager.speaking:
                # No need to actually reply.
                role.context.chat_context_append({"role": "user", "name": "host", "content": f"Host says to you: No, {talk_manager.speaking} is speaking."})
            else:
                role.context.chat_context_append({"role": "assistant", "content": full_response_content})
                talk_manager.speaking = role_name
                response = talk_manager.roles[role_name].chat(
                    message={
                        "role": "user",
                        "name": "host",
                        "content": f"Host says to you: Yes, you are {role_name}, you can talk now. Reply directly with what you want to say, without additionally thanking the host.",
                    }
                )
                async_talk_stream_response = async_iterable_from_gpt(response)
                talk_content = await self.stream_response_display_and_result(role_name=role_name, async_stream_response=async_talk_stream_response, talk_manager=talk_manager)
                TalkToAll = talk_manager.manager.get_job("TalkToAll")
                await self_handler.put_job(TalkToAll(message_content=talk_content, message_from=role_name))

    async def stream_response_result(self, async_stream_response: AsyncIterable) -> str:
        chunk_list = []
        async for chunk in async_stream_response:
            if not chunk:
                continue
            chunk_content = chunk.get("content")
            if not chunk_content:
                continue
            chunk_list.append(chunk_content)
        full_response_content = ''.join(chunk_list)
        return full_response_content      

    async def stream_response_display_and_result(self, role_name: str, async_stream_response: AsyncIterable, talk_manager) -> str:
        chunk_list = []
        async for chunk in async_stream_response:
            if not chunk:
                continue
            chunk_content = chunk.get("content")
            if not chunk_content:
                continue
            await response_auxiliary_message_signal.send_async(
                self,
                _sync_wrapper=sync_wrapper,
                message={
                    "content": {
                        "flag": "content",
                        "content": {"role": "assistant", "name": role_name, "content": chunk_content, "group_talk_manager_id": talk_manager.group_talk_manager_id},
                    },
                    "flag": "group_talk_response",
                },
            )
            chunk_list.append(chunk_content)
        full_response_content = ''.join(chunk_list)
        await response_auxiliary_message_signal.send_async(
            self,
            _sync_wrapper=sync_wrapper,
            message={
                "content": {
                    "flag": "end",
                    "content": {"role": "assistant", "name": role_name, "content": "", "group_talk_manager_id": talk_manager.group_talk_manager_id},
                },
                "flag": "group_talk_response",
            },
        )
        return full_response_content
