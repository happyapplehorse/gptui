from __future__ import annotations
import logging
import openai
import string
import uuid
from typing import TYPE_CHECKING

from ..models.signals import notification_signal
from ..models.openai_chat import OpenaiContext
from ..utils.my_text import MyText as Text
from ..views.animation import AnimationRequest


if TYPE_CHECKING:
    from ..views.tui import MainApp


gptui_logger = logging.getLogger("gptui_logger")


class Notification:
    def __init__(self, app: MainApp):
        self.app = app
        self.displayer = app.query_one("#status_region")
        notification_signal.connect(self.notification_display)
        self.commander_status = {}

    async def notification_display(self, sender, **kwargs) -> None:
        notification = kwargs["message"]
        content = notification["content"]
        flag = notification["flag"]

        if flag == "info":
            info_content = content["content"]
            description = remove_punctuation(content["description"]).lower()
            if description == "raw":
                self.displayer.update(Text(info_content, "green"))
            elif description == "starting to send the original chat message from the user":
                context = info_content["context"]
                self.app.post_message(
                    AnimationRequest(
                        ani_id=context.id,
                        action="start",
                        ani_type=self.app.config["tui_config"]["waiting_receive_animation"],
                    )
                )
            elif description == "an error occurred in communication with openai initiated by user":
                context = info_content["context"]
                self.app.post_message(AnimationRequest(ani_id=context.id, action="end"))
            elif description == "starting to receive the original response message to the user":
                context = info_content["context"]
                self.app.post_message(AnimationRequest(ani_id=context.id, action="end"))
            elif description == "commander exit":
                commander_status_display = self.app.query_one("#commander_status_display")
                commander_status_display.update(Text('\u260a', 'cyan'))
            elif description == "job status changed":
                await self._handle_job_status_changed(info_content=info_content)
            elif description == "grouptalkmanager status changed":
                tab_id = int(self.app.query_one("#chat_tabs").active[3:])
                status = info_content["status"]
                group_talk_manager_id = info_content["group_talk_manager"].group_talk_manager_id
                commander_status_display = self.app.query_one("#commander_status_display")
                self.commander_status[group_talk_manager_id] = status
                if tab_id == group_talk_manager_id:
                    if status is True:
                        commander_status_display.update(Text('\u2725', 'green'))
                        self.displayer.update(Text("Group talk created.", "green"))
                    else:
                        commander_status_display.update(Text('\u2668', 'red'))
                        self.displayer.update(Text("Group talk closed.", "green"))

        elif flag == "warning":
            ani_id = uuid.uuid4()
            self.app.post_message(
                AnimationRequest(
                    ani_id=ani_id,
                    action="start",
                    ani_type="static",
                    keep_time=3,
                    ani_end_display=self.app.status_region_default,
                    others=Text(f"{content}", "yellow"),
                )
            )

        elif flag == "error":
            ani_id = uuid.uuid4()
            self.app.post_message(
                AnimationRequest(
                    ani_id=ani_id,
                    action="start",
                    ani_type="static",
                    keep_time=3,
                    ani_end_display=self.app.status_region_default,
                    others=Text(f"{content}", "red"),
                )
            )
        
        elif flag == "openai_error":
            error = content["error"]
            context = content["context"]
            self.openai_error_display(error=error, context=context)

    async def _handle_job_status_changed(self, info_content: dict):
        tab_id = int(self.app.query_one("#chat_tabs").active[3:])
        status = info_content["status"]
        context_id = info_content["context"].id
        commander_status_display = self.app.query_one("#commander_status_display")
        self.commander_status[context_id] = status
        
        if tab_id != context_id:
            return
        
        if status is True:
            commander_status_display.update(Text('\u260d', 'red'))
            return
        
        self.displayer.update(self.app.status_region_default)
        commander_status_display.update(Text('\u260c', 'yellow'))
        await self.app.chat_context.chat_context_vectorize()
        commander_status_display.update(Text('\u260c', 'green'))
        
        conversation = self.app.openai.conversation_dict.get(context_id)
        if conversation is None:
            return
        
        # AICare
        if self.app.query_one("#ai_care_switch").value is True:
            self.app.openai.accept_ai_care = True
            self.app.openai.ai_care.chat_update(conversation["openai_context"])
        
        # Tab rename
        context = conversation["openai_context"]
        self.app.conversation_tab_rename(context)

    def openai_error_display(self, error: Exception, context: OpenaiContext) -> None:
        app = self.app
        keep_time = 1
        ani_id = context.id
        if isinstance(error, openai.APIStatusError):
            text = Text(f"OpenAI APIStatusError: {error}", "red")
            app.post_message(AnimationRequest(ani_id = ani_id, action = "start", ani_type="static", keep_time=keep_time, priority=0, ani_end_display=text, others=text))
            gptui_logger.error(f"OpenAI APIStatusError: {error}")
        elif isinstance(error, openai.APITimeoutError):
            text = Text(f"OpenAI APITimeoutError: {error}", "red")
            app.post_message(AnimationRequest(ani_id = ani_id, action = "start", ani_type="static", keep_time=keep_time, priority=0, ani_end_display=text, others=text))
            gptui_logger.error(f"OpenAI APITimeoutError: {error}")
        elif isinstance(error, openai.APIConnectionError):
            text = Text(f"OpenAI APIConnectionError: {error}", "red")
            app.post_message(AnimationRequest(ani_id = ani_id, action = "start", ani_type="static", keep_time=keep_time, priority=0, ani_end_display=text, others=text))
            gptui_logger.error(f"OpenAI APIConnectionError: {error}")
        else:
            text = Text(f"Unknown error occurred: {error}", "red")
            app.post_message(AnimationRequest(ani_id = ani_id, action = "start", ani_type="static", keep_time=keep_time, priority=0, ani_end_display=text, others=text))
            gptui_logger.error(f"Unknown error occurred: {error}")


def remove_punctuation(s: str):
    return s.translate(str.maketrans('', '', string.punctuation))
