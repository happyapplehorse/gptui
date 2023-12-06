import logging

from .blinker_wrapper import async_wrapper_with_loop, async_wrapper_without_loop
from .context import OpenaiContext
from .signals import notification_signal


gptui_logger = logging.getLogger("gptui_logger")


class OpenaiErrorHandler:
    def openai_error_handle(self, error: Exception, context: OpenaiContext, event_loop: bool = True, **kwargs) -> None:
        if event_loop is True:
            gptui_logger.error(f"Openai Error: {error}")
            notification_signal.send(self, _async_wrapper=async_wrapper_with_loop, message={"content":{"error":error, "context":context, "ps":kwargs}, "flag":"openai_error"})
        else:
            gptui_logger.error(f"Openai Error: {error}")
            notification_signal.send(self, _async_wrapper=async_wrapper_without_loop, message={"content":{"error":error, "context":context, "ps":kwargs}, "flag":"openai_error"})
