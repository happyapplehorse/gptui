import logging
from typing import Iterable

from .context import Context
from ..gptui_kernel.kernel import Job, Callback, PASS_WORD, tasker
from ..gptui_kernel.manager import ManagerInterface


gptui_logger = logging.getLogger("gptui_logger")


class ResponseJob(Job):
    def __init__(self, manager: ManagerInterface, response: Iterable, context: Context, callback: Callback | None = None):
        super().__init__(callback=callback)
        self.response = response
        self.context = context
        self.manager = manager

    @tasker(PASS_WORD)
    async def task(self):
        ResponseHandler = self.manager.get_handler("ResponseHandler")
        handler = ResponseHandler(self.manager, self.context).handle_response(response=self.response, callback=self.callback)
        return handler
