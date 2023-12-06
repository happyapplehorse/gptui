import logging
import json
import threading
import time

from agere.commander import Callback
from semantic_kernel.orchestration.sk_context import SKContext
from semantic_kernel.skill_definition import sk_function, sk_function_context_parameter

from gptui.gptui_kernel.manager import ManagerInterface, auto_init_params
from gptui.models.blinker_wrapper import async_wrapper_with_loop, sync_wrapper
from gptui.models.openai_chat_inner_service import chat_service_for_inner
from gptui.models.openai_error import OpenaiErrorHandler
from gptui.models.signals import response_auxiliary_message_signal, notification_signal
from gptui.models.utils.openai_api import openai_api
from gptui.utils.my_text import MyText as Text

gptui_logger = logging.getLogger("gptui_logger")


class SnoozeReminder:
    def __init__(self, manager: ManagerInterface):
        self.manager = manager
        self.openai_api = openai_api(manager.dot_env_config_path)
    
    @auto_init_params("0")
    @classmethod
    def get_init_params(cls, manager) -> tuple:
        return (manager,)

    @sk_function(
        description="Set a reminder. When the time comes, you will be notified of the content you set.",
        name="snooze_reminder",
    )
    @sk_function_context_parameter(
        name="delay",
        description="Set the delay for the reminder, in seconds.",
    )
    @sk_function_context_parameter(
        name="reminder_content",
        description="Content to be reminded."
    )
    @sk_function_context_parameter(
        name="openai_context",
        description=(
            "The dictionary string version of the OpenaiContext instance. "
            "This is a special parameter that typically doesn't require manual intervention, as it is usually automatically managed."
            "Unless there's a clear intention, please keep its default value."
        ),
        default_value="AUTO"
    )
    def snooze_reminder(self, context: SKContext) -> str:
        delay = context["delay"]
        
        try:
            delay = int(delay)
        except ValueError:
            return "The parameter 'delay' cannot be parsed into integer seconds."

        content = context["reminder_content"]
        openai_context_dict = json.loads(str(context["openai_context"]))
        conversation_id = openai_context_dict["id"]
        
        reminder = threading.Timer(delay, self.reminder_after, args=(content, conversation_id, delay))
        reminder.start()
        return "The reminder has been set."

    def reminder_after(self, content: str, conversation_id: int | str, delay: int) -> None:
        content = f"You(!not the user!) set a reminder {str(delay)} seconds ago, and the {str(delay)} seconds have elapsed. The time is up.\n==========REMINDER CONTENT BEGIN==========\n" + content
        content += "\n==========REMINDER CONTENT END==========\nThis message is a reminder for you, not for the user. You should handle this message appropriately based on the conversation history."
        openai_chat_manager = self.manager.client.openai
        conversation = openai_chat_manager.conversation_dict.get(conversation_id)
        if conversation is None:
            self.manager.client.query_one("#status_region").update(Text("You have a reminder whose time has come, but it seems the conversation has been closed.", "yellow"))
            gptui_logger.info("You have a reminder whose time has come, but it seems the conversation has been closed.")
        openai_context = conversation["openai_context"]
        self.manager.client.query_one("#chat_tabs").active = "lqt" + str(conversation_id)
        time.sleep(1)
        functions = self.manager.available_functions_meta
        messages_list=[
            {
                "role": "function",
                "name": "snooze_reminder",
                "content": content,
            }
        ]
        response_auxiliary_message_signal.send(
            self,
            message={
                "content":{
                        "role": "function",
                        "name": "snooze_reminder",
                        "content": content,
                },
                "flag": "function_call",
            }
        )

        try:
            response = chat_service_for_inner(
                messages_list=messages_list,
                context=openai_context,
                openai_api=self.openai_api,
                functions=functions,
                function_call="auto",
            )
        except Exception as e:
            OpenaiErrorHandler().openai_error_handle(error=e, context=openai_context)
        
        openai_chat_manager.openai_chat.chat_messages_extend(messages_list=messages_list, context=openai_context)
        
        ResponseJob = self.manager.get_job("ResponseJob")
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
                                    "content":{"status":True},
                                    "description":"Commander status changed",
                                },
                                "flag":"info",
                            },
                        },
                    },
                },
            ],
            at_commander_end=[
                {
                    "function": notification_signal.send_async,
                    "params": {
                        "args": (self,),
                        "kwargs": {
                            "_sync_wrapper": sync_wrapper,
                            "message":{
                                "content":{
                                    "content":{"status":False},
                                    "description":"Commander status changed",
                                },
                                "flag":"info",
                            },
                        },
                    },
                },
            ],
        )
        job = ResponseJob(manager=self.manager, response=response, context=openai_context, callback=callback)
        self.manager.gk_kernel.commander.async_commander_run(job)
