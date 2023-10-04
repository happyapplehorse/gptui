import copy
import json
import logging
import math
import os
import time
from dataclasses import asdict

import openai
from semantic_kernel.connectors.ai.open_ai import OpenAITextEmbedding

from ..gptui_kernel.manager import ManagerInterface
from ..models.context import OpenaiContext
from ..models.openai_chat import OpenaiChatInterface
from ..models.utils.tokens_num import tokens_num_from_chat_context
from ..utils.my_text import MyText as Text
from ..utils.openai_settings_from_dot_env import openai_settings_from_dot_env
from ..views.animation import AnimationRequest
from ..views.screens import InputDialog


openai_key, org_id = openai_settings_from_dot_env()
openai.api_key = openai_key
gptui_logger = logging.getLogger("gptui_logger")


class OpenaiChatManage:
    """
    Schema for conversations:
    {conversation_id:{
        "tab_name": tab_name,
        "file_id": file_id,
        "openai_context": openai_context,
        "bead": {
                "positions": index list of beads,
                "content": dict or list[dict], openai message or list of message which express the bead content,
                "length": list of bead's tokens num,
            },
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
                        # retrieve plugins set
                        openai_context_build["plugins"] = plugins_from_name(
                            manager=manager,
                            plugin_path=app.config["PLUGIN_PATH"],
                            plugins_name_list=conversation_plugins_dict[key],
                        )
                        #openai_context_build["plugins"] = set(openai_context_build["plugins"])
                        value["openai_context"] = OpenaiContext(**openai_context_build)
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

    def init_volatile_memory(self):
        kernel = self.manager.services.sk_kernel
        kernel.add_text_embedding_generation_service("ada", OpenAITextEmbedding("text-embedding-ada-002", openai_key, org_id or ""))
        kernel.register_memory_store(memory_store=self.app.qdrant_vector)

    def bead_insert(self, conversation_id: int | None = None) -> OpenaiContext:
        "Insert the bead into the chat context."
        if conversation_id is None:
            conversation_id = self.conversation_active
        conversation = self.conversation_dict[conversation_id]
        openai_context = conversation["openai_context"]
        bead = conversation["bead"]
        bead_content = bead["content"]
        if openai_context.chat_context is None:
            bead["positions"] = [0]
            bead["length"] = []
        else:
            bead["positions"].append(len(openai_context.chat_context))
        if isinstance(bead_content, dict):
            self.openai_chat.chat_message_append(context=openai_context, message=bead_content)
            bead["length"].append(tokens_num_from_chat_context(chat_context=[bead_content], model=openai_context.parameters["model"]))
        else:
            self.openai_chat.chat_messages_extend(context=openai_context, messages_list=bead_content)
            bead["length"].append(tokens_num_from_chat_context(chat_context=bead_content, model=openai_context.parameters["model"]))
        return openai_context

    def auto_bead_insert(self, conversation_id: int | None = None) -> tuple[OpenaiContext, bool]:
        "Auto insert the bead into the chat context."
        if conversation_id is None:
            conversation_id = self.conversation_active
        conversation = self.conversation_dict[conversation_id]
        if bead_positions := conversation["bead"]["positions"]:
            last_position = bead_positions[-1]
        else:
            last_position = 0
        
        tokens_num_without_bead = sum(conversation["openai_context"].tokens_num_list[last_position:])
        max_sending_tokens_ratio = conversation["max_sending_tokens_ratio"]
        model = conversation["openai_context"].parameters["model"]
        tokens_window = self.app.config["openai_model_info"][model]["tokens_window"]
        max_sending_tokens_num = conversation["openai_context"].max_sending_tokens_num
        
        if tokens_num_without_bead >= max_sending_tokens_num * 0.95:
            app = self.app
            openai_context = self.bead_insert(conversation_id=conversation_id)
            app.query_one("#status_region").update(Text("Bead inserted.","green"))
            #refresh dashboard
            model = conversation["openai_context"].parameters["model"]
            app.dash_board.dash_board_display(tokens_num_window=app.get_tokens_window(model))
            return openai_context, True
        return conversation["openai_context"], False
    
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
        openai_context = OpenaiContext()
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
            "bead":{"content":bead_init, "positions": [], "length": []},
            "max_sending_tokens_ratio": max_sending_tokens_ratio,
        }
        
        # insert initial bead
        self.bead_insert(self.conversation_count)
        self.conversation_id_set.add(self.conversation_count)
        return self.conversation_count
    
    def open_conversation_with_mode(
        self,
        id: int | str | None = None,
        mode: str | None = None,
        openai_params: dict | None = None,
        max_sending_tokens_ratio: float | None = None
        ) -> int:
        """
        open a conversation with mode:
            "Normal": 
        """
        if mode is None:
            mode = "Normal"
        conversation_id = self.open_conversation(id=id, openai_params=openai_params, max_sending_tokens_ratio=max_sending_tokens_ratio)
        if mode == "Normal":
            pass
        return conversation_id
    
    def bead_init(self, bead_id: int) -> dict:
        """
        Generate a initial template bead.
        """
        bead = {"role":"user", "content":f"Memo:\nYour memory is limited. When encountering important information, you should use memo to record it.\nCONVERSATION ID: {bead_id}"}
        return bead

    def conversation_delete(self, conversation_id: int = 0) -> None:
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
                self.app.query_one("#status_region").update(Text(f"Save conversation failed: {e}", "red"))
                gptui_logger.error(f"Write conversation failed. Error: {e}")
                return e
        self.app.query_one("#status_region").update(Text(f"Save conversation context successfully.", "green"))
        self.app.query_one("#conversation_tree").conversation_refresh()
        return True
    
    def read_conversation(self, file_path: str) -> tuple[bool, Exception | int | str]:
        "load conversation from file"
        if not file_path.endswith('.json'):
            self.app.query_one("#status_region").update(Text("Conversation file is not supported.",'yellow'))
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
                self.app.query_one("#status_region").update(Text("File not found",'yellow'))
                return False, e
            except IsADirectoryError as e:
                gptui_logger.error("Specified path is a directory, not a file")
                self.app.query_one("#status_region").update(Text("Specified path is a directory, not a file",'yellow'))
                return False, e
            except UnicodeDecodeError as e:
                gptui_logger.error("File is not encoded properly")
                self.app.query_one("#status_region").update(Text("File is not encoded properly",'yellow'))
                return False, e
            except IOError as e:
                self.app.query_one("#status_region").update(Text(f"An I/O error occurred: {e}",'yellow'))
                gptui_logger.error(f"An I/O error occurred: {e}")
                return False, e
            except Exception as e:
                self.app.query_one("#status_region").update(Text('Read conversation failed','red'))
                gptui_logger.error("Read conversation failed. An unexpected error occurred: {e}")
                return False, e
            else:
                openai_context_build = conversation["openai_context"]
                openai_context = OpenaiContext(**openai_context_build)
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


def plugins_from_name(manager: ManagerInterface, plugin_path: str, plugins_name_list) -> list[tuple]:
    semantic_plugins_list, native_plugins_list = manager.scan_plugins(plugin_path)
    semantic_plugins_dict = {plugin.plugin_info[1]: plugin.plugin_info for plugin in semantic_plugins_list}
    native_plugins_dict = {plugin.plugin_info[2]: plugin.plugin_info for plugin in native_plugins_list}
    # retrieve plugin_info
    default_plugins_used_ready = [d[k] for d in [semantic_plugins_dict, native_plugins_dict] for k in plugins_name_list if k in d]
    return default_plugins_used_ready

def openai_api():
    return openai
