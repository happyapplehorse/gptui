import copy
import json
import logging
import math
import os
import random
import time
from dataclasses import asdict
from typing import Literal, Generator, Iterable

from agere.commander import Callback
from ai_care import AICare, AICareContext
from semantic_kernel.connectors.ai.open_ai import OpenAITextEmbedding

from .ai_care_sensors import time_now
from ..gptui_kernel.manager import ManagerInterface
from ..models.blinker_wrapper import async_wrapper_with_loop, async_wrapper_without_loop
from ..models.context import BeadOpenaiContext, OpenaiContext
from ..models.jobs import GroupTalkManager
from ..models.openai_chat import OpenaiChatInterface, OpenAIGroupTalk
from ..models.openai_chat_inner_service import chat_service_for_inner
from ..models.signals import (
    notification_signal,
    response_to_user_message_stream_signal,
    chat_context_extend_signal,
    response_to_user_message_sentence_stream_signal,
)
from ..models.utils.openai_settings_from_dot_env import openai_settings_from_dot_env
from ..models.utils.openai_api import openai_api_client
from ..utils.my_text import MyText as Text
from ..views.animation import AnimationRequest
from ..views.screens import InputDialog


gptui_logger = logging.getLogger("gptui_logger")


class OpenaiChatManage:
    """
    Schema for conversations:
    {
        conversation_id: {
            "tab_name": tab_name,
            "file_id": file_id,
            "openai_context": BeadOpenaiContext,
            "max_sending_tokens_ratio": the proportion or the maximum number of tokens sent to the total tokens window,
        }
    }
    Schema for group talk conversations:
    {
        conversation_id: {
            "tab_name": tab_name,
            "file_id": file_id,
            "group_talk_manager": GroupTalkManager,
            "max_sending_tokens_ratio": the proportion or the maximum number of tokens sent to the total tokens window,
        }
    }
    """

    def __init__(
        self,
        app,
        manager: ManagerInterface,
        openai_chat: OpenaiChatInterface,
        workpath: str,
        conversations_recover: bool = False,
        vector_memory: bool = True,
    ) -> None:
        assert manager.dot_env_config_path is not None
        self.openai_api_key, self.openai_org_id = openai_settings_from_dot_env(manager.dot_env_config_path)
        # check if workpath is a valid directory
        if not os.path.isdir(workpath):
            if os.path.exists(workpath):
                raise ValueError("'workpath' is not a directory.")
            else:
                os.makedirs(workpath)
        self.app = app
        self.openai_chat = openai_chat
        self.manager = manager
        self.workpath = workpath or os.path.join(app.workpath, "conversations")
        self.conversation_dict = {}
        self.conversation_count = 0
        self.conversation_active = 0
        self.group_talk_conversation_active = 0
        self.conversation_id_set = set()
        if conversations_recover:
            try:
                file_path = os.path.join(workpath, '_conversations_cache.json')
                with open(file_path, "r") as read_file:
                    json_str = read_file.read()
                    conversation_cache = json.loads(json_str)
                    conversation_plugins_dict = conversation_cache["conversation_plugins_dict"]
                    old_conversation_dict = conversation_cache["conversation_dict"]
                    new_conversation_dict = {}
                    for key, value in old_conversation_dict.items():
                        # rebuild OpenaiContext
                        openai_context_build = value["openai_context"]
                        # retrieve plugins list
                        openai_context_build["plugins"] = plugins_from_name(
                            manager=manager,
                            plugin_path=app.config["PLUGIN_PATH"],
                            plugins_name_list=conversation_plugins_dict[key],
                        )
                        value["openai_context"] = BeadOpenaiContext(**openai_context_build)
                        # convert id to int
                        new_conversation_dict[int(key)] = value
                        self.conversation_id_set.add(int(key))
                    self.conversation_dict = new_conversation_dict
                    self.conversation_active = int(conversation_cache["conversation_active"])
            except Exception as e:
                text = Text(f"{type(e).__name__}    " + "Read conversation cache failed, opened a new conversation.", "red")
                app.post_message(AnimationRequest(
                    ani_id="read conversation cache failed",
                    action="start",
                    ani_type="static",
                    keep_time=5,
                    priority=0,
                    ani_end_display=text,
                    others=text,
                ))
                gptui_logger.warning(f"Read conversation cache failed, opened a new conversation: {e}")
                id = self.open_conversation_with_mode()
                self.conversation_active = id
        else:
            id = self.open_conversation_with_mode()
            self.conversation_active = id

        if vector_memory is True:
            self.init_volatile_memory()
        
        self.openai_group_talk = OpenAIGroupTalk(manager=manager)
        self.group_talk_conversation_dict = {}
        self.openai_client = openai_api_client(manager.dot_env_config_path)
        self.ai_care = AICare()
        self._set_ai_care(self.ai_care)
        self.accept_ai_care: bool = True
        self.ai_care_depth_default = app.config["tui_config"]["ai_care_depth"]
        self.ai_care_depth: int = self.ai_care_depth_default

    def reset_ai_care_depth(self):
        if self.ai_care_depth_default <= 1:
            self.ai_care_depth = self.ai_care_depth_default
        else:
            self.ai_care_depth = random.randint(1, self.ai_care_depth_default)

    def _set_ai_care(self, ai_care: AICare):
        ai_care.set_config(key="delay", value=self.app.config["tui_config"]["ai_care_delay"])
        ai_care.set_guide("You are a very considerate person who cares about others and is willing to inntiate conversations")
        ai_care.register_to_llm_method(self.ai_care_to_openai)
        ai_care.register_to_user_method(self.ai_care_to_user)
        self._register_sensors(ai_care)

    def _register_sensors(self, ai_care: AICare):
        ai_care.register_sensor(
            name="time_now",
            function=time_now,
            annotation="Get the current date and time in the local time zone"
        )

    def init_volatile_memory(self):
        kernel = self.manager.services.sk_kernel
        kernel.add_text_embedding_generation_service("ada", OpenAITextEmbedding("text-embedding-ada-002", self.openai_api_key, self.openai_org_id or ""))
        kernel.register_memory_store(memory_store=self.app.qdrant_vector)

    def bead_insert(self, conversation_id: int | None = None) -> BeadOpenaiContext:
        "Insert the bead into the chat context."
        if conversation_id is None:
            conversation_id = self.conversation_active
        conversation = self.conversation_dict[conversation_id]
        openai_context = conversation["openai_context"]
        openai_context.insert_bead()
        return openai_context

    def auto_bead_insert(self, conversation_id: int | None = None) -> tuple[BeadOpenaiContext, bool]:
        "Auto insert the bead into the chat context."
        if conversation_id is None:
            conversation_id = self.conversation_active
        conversation = self.conversation_dict[conversation_id]
        openai_context = conversation["openai_context"]
        do_insert = openai_context.auto_insert_bead()
        
        if do_insert:
            app = self.app
            app.main_screen.query_one("#status_region").update(Text("Bead inserted.","green"))
            #refresh dashboard
            model = conversation["openai_context"].parameters["model"]
            app.dash_board.dash_board_display(tokens_num_window=app.get_tokens_window(model))
            return openai_context, True
        return openai_context, False
    
    def bead_init(self, bead_id: int) -> dict:
        """
        Generate a initial template bead.
        """
        bead = {
            "role": "system",
            "content": (
                "Memo:\nYour memory is limited. When encountering important information, you should use memo to record it.\n"
                f"CONVERSATION ID: {bead_id}"
            )
        }
        return bead
    
    def open_conversation(
        self,
        id: int | str | None = None,
        openai_params: dict | None = None,
        max_sending_tokens_ratio: float | None = None
    ) -> int:
        """
        Open a empty conversation, and return the conversation's id.
        Conversation active id should be handle manually
        """
        self.conversation_count = id or time.time() * 1000
        self.conversation_count = int(self.conversation_count)
        while self.conversation_count in self.conversation_id_set or self.conversation_count == 0:
            assert True, "The conversation_id is duplicated."
            self.conversation_count += 1
        bead_init = self.bead_init(self.conversation_count)
        openai_context = BeadOpenaiContext(bead=[bead_init])
        openai_context.id = self.conversation_count
        openai_context.chat_context = []
        openai_context.plugins = plugins_from_name(manager=self.manager, plugin_path=self.app.config["PLUGIN_PATH"], plugins_name_list=self.app.config["default_plugins_used"])
        
        if openai_params is not None:
            openai_context.parameters = openai_params.copy()
        else:
            openai_context.parameters = self.app.config["default_openai_parameters"].copy()
        openai_context.chat_context_saver = "outer"
        openai_context.chat_context_saver_for_sending = "outer"
        
        if max_sending_tokens_ratio is None:
            max_sending_tokens_ratio = self.app.config["default_conversation_parameters"]["max_sending_tokens_ratio"]
        # check max_sending_tokens_num validity
        if not isinstance(max_sending_tokens_ratio, float):
            raise TypeError("'max_sending_tokens_ratio' have to be a flat number.")
        if not 0.0 < max_sending_tokens_ratio < 1.0:
            raise ValueError("'max_sending_tokens_ratio' have to be in range from 0.0 to 1.0.")

        # set max_sending_tokens_num
        tokens_window = self.app.config["openai_model_info"][openai_context.parameters["model"]]["tokens_window"]
        openai_context.max_sending_tokens_num = math.floor(max_sending_tokens_ratio * tokens_window)
        # set max_tokens
        if openai_context.parameters.get("max_tokens") is None:
            openai_context.parameters["max_tokens"] = tokens_window - openai_context.max_sending_tokens_num
        
        self.conversation_dict[self.conversation_count] = {
            "tab_name": "New",
            "file_id": None,
            "openai_context": openai_context,
            "max_sending_tokens_ratio": max_sending_tokens_ratio,
        }
        
        # insert initial bead
        self.bead_insert(self.conversation_count)
        self.conversation_id_set.add(self.conversation_count)
        return self.conversation_count
    
    def open_conversation_with_mode(
        self,
        id: int | str | None = None,
        mode: Literal["Normal"] | None = None,
        openai_params: dict | None = None,
        max_sending_tokens_ratio: float | None = None
        ) -> int:
        """
        open a conversation with mode:
            "Normal"
        """
        if mode is None:
            mode = "Normal"
        conversation_id = self.open_conversation(id=id, openai_params=openai_params, max_sending_tokens_ratio=max_sending_tokens_ratio)
        if mode == "Normal":
            pass
        return conversation_id

    def delete_conversation(self, conversation_id: int = 0) -> None:
        "delete a conversation from conversation dict"
        if conversation_id == 0:
            conversation_id = self.conversation_active
        del self.conversation_dict[conversation_id]
    
    async def write_conversation(self, conversation_id: int) -> bool | Exception:
        "write a conversation to file"
        file_id = self.conversation_dict[conversation_id]["file_id"] 
        if not file_id:
            self.get_file_id_and_save(conversation_id)
            return False
        
        conversation = copy.deepcopy(self.conversation_dict[conversation_id])

        # Do not save plugins information
        # Clear the plugin list to avoid errors, because when the plugin list contains a Manager object, 'asdict' will raise an error.
        conversation["openai_context"].plugins = []
        # Replace openai_context object with dict version for serialization
        conversation["openai_context"] = asdict(conversation["openai_context"])
        
        with open(os.path.join(self.workpath, str(file_id) + '.json'), "w") as write_file:
            try:
                write_file.write(json.dumps({conversation_id: conversation}, ensure_ascii = False, sort_keys = True, indent = 4, separators = (',',':')))
            except Exception as e:
                self.app.main_screen.query_one("#status_region").update(Text(f"Save conversation failed: {e}", "red"))
                gptui_logger.error(f"Write conversation failed. Error: {e}")
                return e
        self.app.main_screen.query_one("#status_region").update(Text(f"Save conversation context successfully.", "green"))
        self.app.main_screen.query_one("#conversation_tree").conversation_refresh()
        return True
    
    def read_conversation(self, file_path: str) -> tuple[bool, Exception | int | str]:
        "load conversation from file"
        if not file_path.endswith('.json'):
            self.app.main_screen.query_one("#status_region").update(Text("Conversation file is not supported.",'yellow'))
            gptui_logger.error("Conversation file is not supported.")
            return False, ValueError("Conversation file is not supported")
        with open(file_path, "r") as read_file:
            try:
                json_str = read_file.read()
                conversation_info = json.loads(json_str)
                conversation_id = list(conversation_info.keys())[0]
                if int(conversation_id) in self.conversation_dict:
                    # The conversation already exists
                    return False, int(conversation_id)
                conversation = conversation_info[conversation_id]
            except FileNotFoundError as e:
                gptui_logger.error("File not found")
                self.app.main_screen.query_one("#status_region").update(Text("File not found",'yellow'))
                return False, e
            except IsADirectoryError as e:
                gptui_logger.error("Specified path is a directory, not a file")
                self.app.main_screen.query_one("#status_region").update(Text("Specified path is a directory, not a file",'yellow'))
                return False, e
            except UnicodeDecodeError as e:
                gptui_logger.error("File is not encoded properly")
                self.app.main_screen.query_one("#status_region").update(Text("File is not encoded properly",'yellow'))
                return False, e
            except IOError as e:
                self.app.main_screen.query_one("#status_region").update(Text(f"An I/O error occurred: {e}",'yellow'))
                gptui_logger.error(f"An I/O error occurred: {e}")
                return False, e
            except Exception as e:
                self.app.main_screen.query_one("#status_region").update(Text('Read conversation failed','red'))
                gptui_logger.error("Read conversation failed. An unexpected error occurred: {e}")
                return False, e
            else:
                openai_context_build = conversation["openai_context"]
                openai_context = BeadOpenaiContext(**openai_context_build)
                openai_parameters = openai_context.parameters
                model = openai_parameters.get("model")
                if model is None:
                    raise ValueError("Field 'model' is not found in conversation.")
                if mode := conversation.get("mode"):
                    id = self.open_conversation_with_mode(id=conversation_id, openai_params=openai_parameters, mode=mode)
                else:
                    id = self.open_conversation(id=conversation_id, openai_params=openai_parameters)
                conversation["openai_context"] = openai_context
                self.conversation_dict[id] = conversation
                self.conversation_active = id
                return True, id

    def get_file_id_and_save(self, conversation_id: int, input_dialog_prompt: str | None = None) -> None:
        "Get file id when write a new context without file id to file"

        # get the existing filenames
        existing_filenames = set()
        for filename in os.listdir(self.workpath):
            if filename.endswith(".json"):
                filename_without_extension = os.path.splitext(filename)[0]
                existing_filenames.add(filename_without_extension)
        
        async def input_handle(input_: tuple[bool, str]) -> None | str:
            status, content = input_
            if status is True:
                if content in existing_filenames:
                    # re-enter
                    self.get_file_id_and_save(conversation_id, input_dialog_prompt="The entered filename already exists, please re-enter.")
                    return
                self.conversation_dict[conversation_id]["file_id"] = content
                status = await self.write_conversation(conversation_id)
                if status is not True:
                    return
                collection = conversation_id
                self.app.qdrant_queue.put(
                    {
                        "action": "collection_save",
                        "content":{
                            "collection_name": str(collection),
                            "event": None,
                        },
                    }
                )
            else:
                return

        tab_name = self.conversation_dict[conversation_id]["tab_name"]
        self.app.push_screen(InputDialog(prompt=input_dialog_prompt or "Enter a name for the conversation:", default_input=tab_name), input_handle)

    def open_group_talk_conversation(
        self,
        id: int | str | None = None,
        max_sending_tokens_ratio: float | None = None,
    ) -> int:
        """
        Open a empty group talk conversation, and return the conversation's id.
        Conversation active id should be handle manually
        """
        self.conversation_count = id or time.time() * 1000
        self.conversation_count = int(self.conversation_count)
        while self.conversation_count in self.conversation_id_set or self.conversation_count == 0:
            assert True, "The conversation_id is duplicated."
            self.conversation_count += 1
        group_talk_manager = GroupTalkManager(manager=self.manager)
        group_talk_manager.group_talk_manager_id = self.conversation_count
        callback = Callback(
            at_job_start=[
                {
                    "function": notification_signal.send,
                    "params": {
                        "args": (self,),
                        "kwargs": {
                            "_async_wrapper": async_wrapper_with_loop,
                            "message": {
                                "content": {
                                    "content": {"status": True, "group_talk_manager": group_talk_manager},
                                    "description": "GroupTalkManager status changed",
                                },
                                "flag": "info",
                            },
                        },
                    },
                },
            ],
            at_terminate=[
                {
                    "function": notification_signal.send,
                    "params": {
                        "args": (self,),
                        "kwargs": {
                            "_async_wrapper": async_wrapper_with_loop,
                            "message": {
                                "content": {
                                    "content": {"status": False, "group_talk_manager": group_talk_manager},
                                    "description": "GroupTalkManager status changed",
                                },
                                "flag": "info",
                            },
                        },
                    },
                },
            ],
            at_job_end=[
                {
                    "function": notification_signal.send,
                    "params": {
                        "args": (self,),
                        "kwargs": {
                            "_async_wrapper": async_wrapper_with_loop,
                            "message": {
                                "content": {
                                    "content": {"status": False, "group_talk_manager": group_talk_manager},
                                    "description": "GroupTalkManager status changed",
                                },
                                "flag": "info",
                            },
                        },
                    },
                },
            ],
        )
        group_talk_manager.add_callback(callback)
        self.group_talk_conversation_dict[self.conversation_count] = {
            "tab_name": "Group-Talk",
            "file_id": None,
            "group_talk_manager": group_talk_manager,
            "max_sending_tokens_ratio": max_sending_tokens_ratio or self.app.config["default_conversation_parameters"]["max_sending_tokens_ratio"],
        }
        self.conversation_id_set.add(self.conversation_count)
        self.group_talk_conversation_active = self.conversation_count
        return self.conversation_count

    def delete_group_talk_conversation(self, group_talk_conversation_id: int = 0) -> None:
        """delete a group talk conversation from group_talk_conversation_dict"""
        if group_talk_conversation_id == 0:
            group_talk_conversation_id = self.group_talk_conversation_active
        group_talk_manager = self.group_talk_conversation_dict[group_talk_conversation_id]["group_talk_manager"]
        group_talk_manager.close_group_talk()
        del self.group_talk_conversation_dict[group_talk_conversation_id]

    def ai_care_to_openai(
        self,
        chat_context: OpenaiContext,
        to_llm_messages: list[AICareContext]
    ) -> Generator[str, None, None]:
        messages_list = [
            {"role": "user", "name": "Aicarey", "content": message["content"]} if message["role"] == "ai_care"
            else {"role": "assistant", "content": message["content"]}
            for message in to_llm_messages
        ]
        openai_response = chat_service_for_inner(
            messages_list=messages_list,
            context=chat_context,
            openai_api_client=self.openai_client,
        )
        def response_gen(response: Iterable):
            for chunk in response:
                content = chunk.choices[0].delta.content
                if content is None:
                    continue
                yield content
        return response_gen(openai_response)

    def ai_care_to_user(self, to_user_message: Generator[str, None, None]) -> None:
        if self.accept_ai_care is False:
            return
        context_id = self.conversation_active
        openai_context = self.conversation_dict[self.conversation_active]["openai_context"]
        char_list = []
        voice_buffer = ""
        first_times = True
        for char in to_user_message:
            response_to_user_message_stream_signal.send(
                self,
                _async_wrapper=async_wrapper_without_loop,
                message={"content": {"content": char.lstrip() if first_times else char, "context_id": context_id}, "flag": "content"},
            )
            char_list.append(char)
            first_times = False
            
            # Send voice signal
            if response_to_user_message_sentence_stream_signal.receivers:
                voice_buffer += char
                if char.startswith((".","!","?",";",":","。","！","？","；","：","\n")):
                    response_to_user_message_sentence_stream_signal.send(
                        self,
                        _async_wrapper=async_wrapper_without_loop,
                        message={"content": voice_buffer, "flag": "content"},
                    )
                    voice_buffer = ""

        response_to_user_message_stream_signal.send(
            self,
            _async_wrapper=async_wrapper_without_loop,
            message={"content": {"content": "", "context_id": context_id}, "flag": "end"},
        )

        chat_context_extend_signal.send(
            self,
            _async_wrapper=async_wrapper_without_loop,
            message={
                "content": {
                    "messages": [{"role": "assistant", "content": ''.join(char_list)}],
                    "context": openai_context,
                },
                "flag": "",
            }
        )
        
        if voice_buffer:
            response_to_user_message_sentence_stream_signal.send(
                self,
                _async_wrapper=async_wrapper_without_loop,
                message={"content": voice_buffer, "flag": "content"},
            )
            voice_buffer = ""

        # Send voice end signal
        if response_to_user_message_sentence_stream_signal.receivers:
            response_to_user_message_sentence_stream_signal.send(
                self,
                _async_wrapper=async_wrapper_without_loop,
                message={"content":"", "flag":"end"}
            )
        
        if self.ai_care_depth > 0:
            self.ai_care.chat_update(openai_context)
            self.ai_care_depth -= 1


def plugins_from_name(manager: ManagerInterface, plugin_path: str, plugins_name_list) -> list[tuple]:
    semantic_plugins_list, native_plugins_list = manager.scan_plugins(plugin_path)
    semantic_plugins_dict = {plugin.plugin_info[1]: plugin.plugin_info for plugin in semantic_plugins_list}
    native_plugins_dict = {plugin.plugin_info[2]: plugin.plugin_info for plugin in native_plugins_list}
    # retrieve plugin_info
    default_plugins_used_ready = [d[k] for d in [semantic_plugins_dict, native_plugins_dict] for k in plugins_name_list if k in d]
    return default_plugins_used_ready
