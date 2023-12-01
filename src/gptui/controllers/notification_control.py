import logging
import openai
import uuid

from ..models.signals import notification_signal
from ..models.openai_chat import OpenaiContext
from ..utils.my_text import MyText as Text
from ..views.animation import AnimationRequest


gptui_logger = logging.getLogger("gptui_logger")


class Notification:
    def __init__(self, app):
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
            description = content["description"]
            if description == "raw":
                self.displayer.update(Text(info_content, "green"))
            elif description == "Starting to send the original chat message from the user.":
                context = info_content["context"]
                self.app.post_message(AnimationRequest(ani_id=context.id, action="start"))
            elif description == "An error occurred in communication with OpenAI initiated by user.":
                context = info_content["context"]
                self.app.post_message(AnimationRequest(ani_id=context.id, action="end"))
            elif description == "Starting to receive the original response message to the user":
                context = info_content["context"]
                self.app.post_message(AnimationRequest(ani_id=context.id, action="end"))
            elif description == "Commander exit":
                commander_status_display = self.app.query_one("#commander_status_display")
                commander_status_display.update(Text('\u260a', 'cyan'))
            elif description == "Job status changed":
                tab_id = int(self.app.query_one("#chat_tabs").active[3:])
                status = info_content["status"]
                context_id = info_content["context"].id
                commander_status_display = self.app.query_one("#commander_status_display")
                self.commander_status[context_id] = status
                if tab_id == context_id:
                    if status is True:
                        commander_status_display.update(Text('\u260d', 'red'))
                    else:
                        self.displayer.update(self.app.status_region_default)
                        commander_status_display.update(Text('\u260c', 'yellow'))
                        await self.app.chat_context.chat_context_vectorize()
                        commander_status_display.update(Text('\u260c', 'green'))
                        # Tab rename
                        conversation = self.app.openai.conversation_dict.get(context_id)
                        if conversation is not None:
                            context = conversation["openai_context"]
                            self.app.conversation_tab_rename(context)
            elif description == "GroupTalkManager status changed":
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
