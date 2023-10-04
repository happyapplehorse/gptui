import logging
import openai

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

    async def notification_display(self, sender, **kwargs) -> None:
        notification = kwargs["message"]
        content =notification["content"]
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
            elif description == "Commander status changed":
                status = info_content["status"]
                commander_status_display = self.app.query_one("#commander_status_display")
                if status is True:
                    commander_status_display.update(Text('\u260d', 'red'))
                else:
                    self.displayer.update(self.app.status_region_default)
                    commander_status_display.update(Text('\u260c', 'yellow'))
                    await self.app.chat_context.chat_context_vectorize()
                    commander_status_display.update(Text('\u260c', 'green'))
        
        elif flag == "warning":
            pass

        elif flag == "error":
            pass
        
        elif flag == "openai_error":
            error = content["error"]
            context = content["context"]
            self.openai_error_display(error=error, context=context)

    def openai_error_display(self, error: Exception, context: OpenaiContext) -> None:
        app = self.app
        keep_time = 1
        ani_id = context.id
        if isinstance(error, openai.error.ServiceUnavailableError):
            text = Text(f"OpenAI servers are not available now: {error}", "red")
            app.post_message(AnimationRequest(ani_id = ani_id, action = "start", ani_type="static", keep_time=keep_time, priority=0, ani_end_display=text, others=text))
            gptui_logger.error(f"OpenAI servers are not available now: {error}")
        elif isinstance(error, openai.error.AuthenticationError):
            text = Text(f"API key or token was invalide, expired, or revoked: {error}", "red")
            app.post_message(AnimationRequest(ani_id = ani_id, action = "start", ani_type="static", keep_time=keep_time, priority=0, ani_end_display=text, others=text))
            gptui_logger.error(f"API key or token was invalide, expired, or revoked: {error}")
        elif isinstance(error, openai.error.InvalidRequestError):
            text = Text(f"Invalid request error: {error}", "red")
            app.post_message(AnimationRequest(ani_id = ani_id, action = "start", ani_type="static", keep_time=keep_time, priority=0, ani_end_display=text, others=text))
            gptui_logger.error(f"Invalid request error: {error}")
        elif isinstance(error, openai.error.Timeout):
            text = Text(f"OpenAI API request Timeout: {error}", "red")
            app.post_message(AnimationRequest(ani_id = ani_id, action = "start", ani_type="static", keep_time=keep_time, priority=0, ani_end_display=text, others=text))
            gptui_logger.error(f"OpenAI API request Timeout: {error}")
        elif isinstance(error, openai.error.APIError):
            text = Text(f"OpenAI API returned an API Error: {error}", "red")
            app.post_message(AnimationRequest(ani_id = ani_id, action = "start", ani_type="static", keep_time=keep_time, priority=0, ani_end_display=text, others=text))
            gptui_logger.error(f"OpenAI API returned an API Error: {error}")
        elif isinstance(error, openai.error.APIConnectionError):
            text = Text(f"Failed to connect to OpenAI API: {error}", "red")
            app.post_message(AnimationRequest(ani_id = ani_id, action = "start", ani_type="static", keep_time=keep_time, priority=0, ani_end_display=text, others=text))
            gptui_logger.error(f"Failed to connect to OpenAI API: {error}")
        elif isinstance(error, openai.error.RateLimitError):
            text = Text(f"OpenAI API request exceeded rate limit: {error}", "red")
            app.post_message(AnimationRequest(ani_id = ani_id, action = "start", ani_type="static", keep_time=keep_time, priority=0, ani_end_display=text, others=text))
            gptui_logger.error(f"OpenAI API request exceeded rate limit: {error}")
        else:
            text = Text(f"Unknown error occurred: {error}", "red")
            app.post_message(AnimationRequest(ani_id = ani_id, action = "start", ani_type="static", keep_time=keep_time, priority=0, ani_end_display=text, others=text))
            gptui_logger.error(f"Unknown error occurred: {error}")
