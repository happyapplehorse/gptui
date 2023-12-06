""" wait for open-interpreter to be compatible with openai version 1.1.1
import asyncio
import logging

from semantic_kernel.skill_definition import sk_function

from gptui.utils.open_interpreter import MyInterpreter, response_render
from gptui.utils.safe_iterate import safe_next, safe_send


gptui_logger = logging.getLogger("gptui_logger")


class OpenInterpreter:

    def __init__(self):
        self.interpreter = MyInterpreter()
        self.in_chat = False
        self.chat = None
        self.result = None

    @sk_function(
        description=(
            "A code assistant that allows for continuous dialogue in natural language. "
            "It can be invoked continuously multiple times"
            "Describe your needs to it, and it will automatically write and execute code to help you accomplish tasks. "
            "When asked whether to execute the code, respond to this function precisely with 'y' or 'n'. "
            "Before responding with 'y', you should first seek the user's consent."
        ),
        name="open_interpreter",
        input_description="Your needs.",
    )
    async def open_interpreter(self, input_request: str) -> str:
        if not self.in_chat:
            self.chat = self.interpreter.chat(str(input_request))
            status, out = await asyncio.to_thread(safe_next, self.chat)
            if status == "OK":
                self.in_chat = True
            else:
                self.in_chat = False
            result = response_render(out)
            gptui_logger.info(f"Open interpreter response: {result}")
            self.new_chat = False
            return result
        else:
            assert self.chat is not None
            status, out = await asyncio.to_thread(safe_send, self.chat, str(input_request))
            if status == "OK":
                self.in_chat = True
            else:
                self.in_chat = False
            result = response_render(out)
            gptui_logger.info(f"Open interpreter response: {result}")
            return result

    @sk_function(
        description=(
            "Terminate the interaction with the open interpreter, resetting it to a fresh state. "
            "Whenever you finish a task with the open interpreter or no longer need it, you should promptly end the interaction with it."
        )
    )
    def end_open_interpreter(self):
        self.interpreter.reset()
        gptui_logger.info("Open interpreter reset.")
        return "Successfully terminated the interaction with the open interpreter."

"""
