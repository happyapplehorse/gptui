import logging
import random
import threading
from typing import Iterable, AsyncIterable

from agere.commander import PASS_WORD, Job, Callback, tasker

from .blinker_wrapper import sync_wrapper
from .context import Context
from .role import Role
from .signals import (
    common_message_signal,
    notification_signal,
    response_auxiliary_message_signal,
)
from ..gptui_kernel.manager import ManagerInterface


gptui_logger = logging.getLogger("gptui_logger")


class ResponseJob(Job):
    def __init__(
        self,
        manager: ManagerInterface,
        response: Iterable,
        context: Context,
        callback: Callback | None = None,
        at_receiving_start: list[dict] | None = None,
        at_receiving_end: list[dict] | None = None,
    ):
        super().__init__(callback=callback)
        self.response = response
        self.context = context
        self.manager = manager
        self.at_receiving_start = at_receiving_start
        self.at_receiving_end = at_receiving_end

    @tasker(PASS_WORD)
    async def task(self):
        ResponseHandler = self.manager.get_handler("ResponseHandler")
        handler = ResponseHandler(self.manager, self.context).handle_response(
            response=self.response,
            at_receiving_start=self.at_receiving_start,
            at_receiving_end=self.at_receiving_end,
        )
        return handler


class GroupTalkManager(Job):
    def __init__(self, manager: ManagerInterface, user_name: str = "admin"):
        self._speaking = None
        self._ai_care_rlock = threading.RLock()
        self.running = False
        self.manager = manager
        self.user_name = user_name
        self.group_talk_manager_id: int | None = None
        self.roles: dict[str, Role] = {}
        self.user_talk_buffer = []
        self.ai_care_message_buffer: list[dict] = []
        super().__init__()
    
    @property
    def speaking(self) -> str | None:
        return self._speaking

    @speaking.setter
    def speaking(self, value: str | None):
        with self._ai_care_rlock:
            if value is None:
                messages = [{"role": "user", "name": self.user_name, "content": message} for message in self.user_talk_buffer]
                if messages:
                    self.ai_care_message_buffer = []
                    self._speaking = self.user_name
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
                    for role in self.roles.values():
                        role.ai_care_update()
            else:
                for role in self.roles.values():
                    role.ai_care.cancel_current_task()
                self.ai_care_message_buffer = []
            self._speaking = value
    
    async def set_speaking_to_none(self):
        with self._ai_care_rlock:
            self.speaking = None
            dose_send = await self.send_ai_care_message()
            if not dose_send:
                for role in self.roles.values():
                    role.ai_care_update()

    async def send_ai_care_message(self) -> bool:
        message = self.ai_care_message_buffer[0] if self.ai_care_message_buffer else None
        subsequent_messages = self.ai_care_message_buffer[1:]
        if message:
            role_name = message["name"]
            self.speaking = role_name
            try:
                message_content = await self.ai_care_response(role_name=role_name, response=message["content"])
            except Exception as e:
                await self.set_speaking_to_none()
                self.ai_care_message_buffer.extend(subsequent_messages)
                gptui_logger.info(f"Encountered an error when receiving the AICare speech content of group chat member {role_name}, error: {e}")
            else:
                await self.put_job(TalkToAll(message_content=message_content, message_from=role_name))
                # self.ai_care_message_buffer = [] # This operation has already been performed when setting speaking=role_name
                return True
        return False

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

    def close_group_talk(self):
        self.running = False
        
    @tasker(PASS_WORD)
    async def task(self):
        self.running = True
        GroupTalkHandler = self.manager.get_handler("GroupTalkHandler")
        return GroupTalkHandler().wait_for_termination(self)

    async def ai_care_response(self, role_name: str, response: AsyncIterable) -> str:
        chunk_list = []
        async for chunk in response:
            if not chunk:
                continue
            await response_auxiliary_message_signal.send_async(
                self,
                _sync_wrapper=sync_wrapper,
                message={
                    "content": {
                        "flag": "content",
                        "content": {
                            "role": "assistant",
                            "name": role_name,
                            "content": chunk,
                            "group_talk_manager_id": self.group_talk_manager_id,
                        },
                    },
                    "flag": "group_talk_response",
                },
            )
            chunk_list.append(chunk)
        full_response_content = ''.join(chunk_list)
        await response_auxiliary_message_signal.send_async(
            self,
            _sync_wrapper=sync_wrapper,
            message={
                "content": {
                    "flag": "end",
                    "content": {"role": "assistant", "name": role_name, "content": "", "group_talk_manager_id": self.group_talk_manager_id},
                },
                "flag": "group_talk_response",
            },
        )
        return full_response_content


class TalkToAll(Job):
    def __init__(self, message_content: str, message_from: str):
        self.message_content = message_content
        self.message_from = message_from
        super().__init__()

    @tasker(PASS_WORD)
    async def task(self):
        talk_manager = self.ancestor_chain[-2]
        assert isinstance(talk_manager, GroupTalkManager)
        if not talk_manager.running:
            return
        response_dict = {}
        all_roles = list(talk_manager.roles.items())
        # Randomly shuffle the order to give each role an equal opportunity to speak.
        random.shuffle(all_roles)
        try:
            for role_name, role in all_roles:
                if role_name == self.message_from:
                    response_dict[role_name] = role.chat(message={"role": "assistant", "content": self.message_content})
                else:
                    response_dict[role_name] = role.chat(message={"role": "user", "name": self.message_from, "content": self.message_content})
        except Exception as e:
            gptui_logger.info(f"Encountered an error when the group chat member {self.message_from} talks to all, error: {e}")
        finally:
            await talk_manager.set_speaking_to_none()
        GroupTalkHandler = talk_manager.manager.get_handler("GroupTalkHandler")
        return GroupTalkHandler().handle_response(response_dict)
