import asyncio
import copy
import json
import logging
from dataclasses import asdict

from .blinker_wrapper import sync_wrapper, async_wrapper_with_loop
from .context import OpenaiContext
from .signals import (
    chat_context_extend_signal,
    notification_signal,
    response_auxiliary_message_signal,
    response_to_user_message_stream_signal,
    response_to_user_message_sentence_stream_signal,
)
from .openai_chat_inner_service import chat_service_for_inner
from .openai_error import OpenaiErrorHandler
from ..gptui_kernel.dispatcher import(
    async_iterable_from_gpt,
    async_dispatcher_function_call,
)
from ..gptui_kernel.manager import ManagerInterface
from ..gptui_kernel.kernel import BasicJob, handler, Callback


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
                message={"content": char, "flag": "content"},
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
            message={"content": "", "flag": "end"},
        )
        
        # save response to context
        if self.chat_context_saver == "outer":
            await chat_context_extend_signal.send_async(
                self,
                _sync_wrapper=sync_wrapper,
                message={
                    "content":{
                        "messages": [{"role":"assistant", "content":collected_messages}],
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
                paras = {"messages_list": message, "context": self.context, "functions": functions, "function_call": "auto"}
            else:
                paras = {"messages_list": message, "context": self.context}
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
                                        "role": "assistant",
                                        "content": (
                                            f"<log />Call function: {function_call_display_str}\n"
                                            "This is just a brief history record of the function you have previously invoked. "
                                            "You should not call functions in this manner, nor should you use the <log /> tag."
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
                            "role": "assistant",
                            "content": (
                                f"<log />Call function: {function_call_display_str}\n"
                                "This is just a brief history record of the function you have previously invoked. "
                                "You should not call functions in this manner, nor should you use the <log /> tag."
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
