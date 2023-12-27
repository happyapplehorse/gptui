import asyncio
import copy
import json
import logging
import random
from dataclasses import asdict
from typing import Iterable, AsyncIterable

from agere.commander import PASS_WORD, BasicJob, handler
from agere.utils.dispatcher import async_dispatcher_tools_call_for_openai
from agere.utils.llm_async_converters import LLMAsyncAdapter

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
from .utils.openai_api import openai_api_client
from ..gptui_kernel.manager import ManagerInterface


gptui_logger = logging.getLogger("gptui_logger")


class ResponseHandler:
    """A handler to handle response from LLM."""
    def __init__(self, manager: ManagerInterface, context: OpenaiContext):
        self.manager = manager
        self.context = context

    @handler(PASS_WORD)
    async def handle_response(
        self,
        self_handler,
        response,
        at_receiving_start: list[dict] | None = None,
        at_receiving_end: list[dict] | None = None,
    ):
        """handler that handle response from LLM"""
        make_role_generator = await async_dispatcher_tools_call_for_openai(
            source=LLMAsyncAdapter(logger=gptui_logger).llm_to_async_iterable(
                response=response,
                at_receiving_start=at_receiving_start,
                at_receiving_end=at_receiving_end,
            ),
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
        self.openai_api_client = openai_api_client(manager.dot_env_config_path)

    @handler(PASS_WORD)
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
                    "content": {
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
    
    @handler(PASS_WORD)
    async def function_call_handler(self, self_handler, function_call_gen) -> None:
        function_result_dict = {}
        async for function_call in function_call_gen:
            if not function_call:
                continue
            function_dict = {}
            try:
                function_dict = json.loads(function_call)
            except json.JSONDecodeError as e:
                gptui_logger.error(f"An error occurred while parsing the JSON string. JSON string: {function_call}. Error: {e}")
            if function_dict.get("name"):
                # call the function
                tool_call_index = function_dict["tool_call_index"]
                tool_call_id = function_dict["tool_call_id"]
                function_name = function_dict["name"]
                function_to_call = self.manager.available_functions_link[function_name]
                function_args = function_dict["arguments"]
                
                await notification_signal.send_async(
                    self,
                    _sync_wrapper=sync_wrapper,
                    message={
                        "content":{
                            "content": f"Function calling{f'({tool_call_index})' if tool_call_index else ''}: " + function_name + " ... ",
                            "description": "raw",
                        },
                        "flag": "info",
                    }
                )

                context = self.manager.gk_kernel.context_render(args=function_args, function=function_to_call)
                
                # Dose insert context
                if context.variables.get("openai_context") == "AUTO":
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
                gptui_logger.info(f"Function call: {function_call_display_str}; ID: {tool_call_id}.")
                function_response_context = await function_to_call.invoke_async(context=context)
                function_response = str(function_response_context)
                function_result_dict[tool_call_index] = {
                    "tool_call_id": tool_call_id,
                    "function_name": function_name,
                    "function_args": function_args,
                    "function_result": function_response,
                }
                await response_auxiliary_message_signal.send_async(
                    self,
                    _sync_wrapper=sync_wrapper,
                    message={
                        "content":
                            {
                                "role": "function",
                                "name": function_name,
                                "content": function_response,
                            },
                        "flag":"function_response",
                    },
                )
        
        if not function_result_dict:
            return
        # send the function response to GPT
        message = [
            {
                "tool_call_id": function_result["tool_call_id"],
                "role": "tool",
                "name": function_result["function_name"],
                "content": function_result["function_result"],
            } for function_result in function_result_dict.values()
        ]
        gptui_logger.info(f"Function response: {message}")
        functions = self.manager.available_functions_meta
        await notification_signal.send_async(
            self,
            _sync_wrapper=sync_wrapper,
            message={
                "content": {
                    "content": "Sent function call result, waiting for response ...",
                    "description": "raw",
                },
                "flag": "info",
            }
        )
        if functions:
            paras = {"messages_list": message, "context": self.context, "openai_api_client": self.openai_api_client, "tools": functions, "tool_choice": "auto"}
        else:
            paras = {"messages_list": message, "context": self.context, "openai_api_client": self.openai_api_client}
        try:
            # add response to context
            if self.chat_context_saver == "outer":
                await chat_context_extend_signal.send_async(
                    self,
                    _sync_wrapper=sync_wrapper,
                    message={
                        "content":{
                            "messages": [
                                {
                                    "role": "assistant",
                                    "content": None,
                                    "tool_calls": [
                                        {"id": one_function_call["tool_call_id"], "function": {"arguments": str(one_function_call["function_args"]), "name": one_function_call["function_name"]}, "type": "function"} for one_function_call in function_result_dict.values()
                                    ]
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
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {"id": one_function_call["tool_call_id"], "function": {"arguments": str(one_function_call["function_args"]), "name": one_function_call["function_name"]}, "type": "function"} for one_function_call in function_result_dict.values()
                        ]
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

        ResponseJob = self.manager.get_job("ResponseJob")
        at_receiving_start = [
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
        ]
        await self_handler.put_job(
            ResponseJob(
                response=response,
                manager=self.manager,
                context=self.context,
                at_receiving_start=at_receiving_start,
            )
        )


class GroupTalkHandler:
    @handler(PASS_WORD)
    async def handle_response(self, self_handler, response_dict: dict[str, Iterable]):
        items = list(response_dict.items())
        # Randomly shuffle the order to give each role an equal opportunity to speak.
        random.shuffle(items)
        for role_name, response in items:
            self_handler.call_handler(self.parse_stream_response(role_name=role_name, stream_response=response))

    @handler(PASS_WORD)
    async def wait_for_termination(self, self_handler, group_talk_manager):
        while True:
            await asyncio.sleep(0.5)
            # If no one is speaking, check if the user is speaking.
            if group_talk_manager.speaking is None:
                messages = [{"role": "user", "name": group_talk_manager.user_name, "content": message} for message in group_talk_manager.user_talk_buffer]
                if messages:
                    with group_talk_manager._ai_care_rlock:
                        group_talk_manager.ai_care_message_buffer = []
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
                    for role in group_talk_manager.roles.values():
                        role.ai_care_update()
                else:
                    # The task might iteratively receive messages and incur certain delays, but that's okay; 
                    # there is a character currently speaking, and it is permissible for the loop to be blocked at this time.
                    with group_talk_manager._ai_care_rlock:
                        await group_talk_manager.send_ai_care_message()
            if not group_talk_manager.running:
                await group_talk_manager.close_task_node()
                group_talk_manager.speaking = None
                break

    @handler(PASS_WORD)
    async def parse_stream_response(self, self_handler, role_name, stream_response):
        async_stream_response = LLMAsyncAdapter().llm_to_async_iterable(stream_response)
        talk_manager = self_handler.ancestor_chain[-2]
        if not talk_manager.running:
            return
        full_response_content = await self.stream_response_result(async_stream_response=async_stream_response)
        role = talk_manager.roles[role_name]
        if "Can I speak" in full_response_content:
            if talk_manager.speaking:
                # No need to actually reply.
                role.context.chat_context_append({"role": "assistant", "content": "Can I speak?"})
                role.context.chat_context_append({"role": "user", "name": "host", "content": f"SYS_INNER: Host says to you: No, {talk_manager.speaking} is speaking."})
                gptui_logger.info(f"{role_name} want to speak, but {talk_manager.speaking} is speaking.")
            else:
                gptui_logger.info(f"{role_name} speak.")
                role.context.chat_context_append({"role": "assistant", "content": "Can I speak?"})
                talk_manager.speaking = role_name
                try:
                    response = talk_manager.roles[role_name].chat(
                        message={
                            "role": "user",
                            "name": "host",
                            "content": f"SYS_INNER: Host says to you: Yes, you are {role_name}, you can talk now. Reply directly with what you want to say, without additionally thanking the host.",
                        }
                    )
                    async_talk_stream_response = LLMAsyncAdapter().llm_to_async_iterable(response)
                    talk_content = await self.stream_response_display_and_result(role_name=role_name, async_stream_response=async_talk_stream_response, talk_manager=talk_manager)
                except Exception as e:
                    # If receiving the message fails, set talk_manager.speaking to None to avoid blocking the group chat.
                    await talk_manager.set_speaking_to_none()
                    gptui_logger.warning(f"Encountered an error when receiving the speech content of group chat member {role_name}, error: {e}")
                else:
                    TalkToAll = talk_manager.manager.get_job("TalkToAll")
                    await self_handler.put_job(TalkToAll(message_content=talk_content, message_from=role_name))
        else:
            role.context.chat_context_append({"role": "assistant", "content": " "})
            if full_response_content and not full_response_content.isspace():
                gptui_logger.info(f"The group talk member {role_name} speak without asking 'Can I speak?' first, full_response_content: {full_response_content}")
            else:
                gptui_logger.info(f"{role_name} stay silent.")

    async def stream_response_result(self, async_stream_response: AsyncIterable) -> str:
        chunk_list = []
        async for chunk in async_stream_response:
            chunk_content = chunk.choices[0].delta.content
            if not chunk_content:
                continue
            chunk_list.append(chunk_content)
        full_response_content = ''.join(chunk_list)
        return full_response_content      

    async def stream_response_display_and_result(self, role_name: str, async_stream_response: AsyncIterable, talk_manager) -> str:
        chunk_list = []
        async for chunk in async_stream_response:
            chunk_content = chunk.choices[0].delta.content
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
