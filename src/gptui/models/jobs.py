import logging
import random
from typing import Iterable

from .blinker_wrapper import async_wrapper_with_loop
from .context import Context
from .role import Role
from .signals import notification_signal, common_message_signal
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


class GroupTalkManager(Job):
    def __init__(self, manager: ManagerInterface):
        self._speaking = None
        self.running = False
        self.manager = manager
        self.group_talk_manager_id: int | None = None
        self.roles: dict[str, Role] = {}
        self.user_talk_buffer = []
        super().__init__()
    
    @property
    def speaking(self) -> str | None:
        return self._speaking

    @speaking.setter
    def speaking(self, value: str | None):
        if value is None:
            messages = [{"role": "user", "name": "host", "content": message} for message in self.user_talk_buffer]
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
                items = list(self.roles.items())
                # Randomly shuffle the order to give each role an equal opportunity to speak.
                random.shuffle(items)
                for role_name, role in items:
                    response_dict[role_name] = role.chat(message=messages)
                GroupTalkHandler = self.manager.get_handler("GroupTalkHandler")
                # Because at any given moment only one role can speak, it is safe when multiple dialogue tasks are running in parallel;
                # there will be no inconsistency in the role's chat history.
                self.call_handler(GroupTalkHandler().handle_response(response_dict))
                self.user_talk_buffer = []
        self._speaking = value

    def create_role(self, role: Role, role_name: str) -> bool:
        if role_name in self.roles:
            notification_signal.send(
                self,
                _async_wrapper=async_wrapper_with_loop,
                message={
                    "content": f"The name of '{role_name}' has already existed.",
                    "flag": "warning",
                }
            )
            return False
        self.roles[role_name] = role
        return True

    async def close_group_talk(self):
        await self.close_task_node()
        self.running = False
        
    @tasker(PASS_WORD)
    async def task(self):
        self.running = True
        GroupTalkHandler = self.manager.get_handler("GroupTalkHandler")
        return GroupTalkHandler().wait_for_termination(self)


class TalkToAll(Job):
    def __init__(self, message_content: str, message_from: str):
        self.message_content = message_content
        self.message_from = message_from
        super().__init__()

    @tasker(PASS_WORD)
    async def task(self):
        gptui_logger.debug(self.message_content)
        talk_manager = self.ancestor_chain[-2]
        assert isinstance(talk_manager, GroupTalkManager)
        if not talk_manager.running:
            return
        response_dict = {}
        items = list(talk_manager.roles.items())
        # Randomly shuffle the order to give each role an equal opportunity to speak.
        random.shuffle(items)
        for role_name, role in items:
            response_dict[role_name] = role.chat(message={"role": "user", "name": self.message_from, "content": self.message_content})
        talk_manager.speaking = None
        GroupTalkHandler = talk_manager.manager.get_handler("GroupTalkHandler")
        return GroupTalkHandler().handle_response(response_dict)
