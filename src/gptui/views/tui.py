import asyncio
import copy
import importlib
import itertools
import json
import logging
import math
import os
import queue
import random
import subprocess
import textwrap
import threading
import uuid
from threading import Thread

import yaml
from dataclasses import asdict
from rich.emoji import Emoji
from textual import work
from textual.app import App, ComposeResult
from textual.actions import ActionError
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, Container
from textual.widgets import (
    Static,
    Label,
    DirectoryTree,
    Button,
    Tabs,
    Tab,
    Tree,
    ContentSwitcher,
    Switch,
    RichLog,
)
from textual.widgets._tabs import Underline

from .animation import AnimationManager, AnimationRequest, DefaultAnimation, StaticDisplayAnimation, SettingMemoryAnimation
from .fun_zone import FunZone, JustBeing, BombBoom
from .mywidgets import (
    GridContent,
    MyFillIn,
    MyMultiInput,
    MyChatWindow,
    MultiGridContent,
    MyCheckBox,
    SlideSwitch,
    Tube,
    AppStart,
    NoPaddingButton,
)
from .screens import CheckDialog, HotKey, MarkdownPreview
from .voice import Voice
from .wink_wink import Horse
from ..controllers.assistant_tube_control import AssistantTube
from ..controllers.chat_context_control import ChatContext
from ..controllers.chat_response_control import ChatResponse
from ..controllers.dash_board_control import DashBoard
from ..controllers.decorate_display_control import DecorateDisplay
from ..controllers.notification_control import Notification
from ..controllers.openai_chat_manage import OpenaiChatManage, openai_api
from ..controllers.tube_files_control import TubeFiles
from ..controllers.voice_control import VoiceService
from ..data.vector_memory.qdrant_memory import QdrantVector
from ..drivers.driver_manager import DriverManager
from ..models.context import OpenaiContext
from ..models.doc import Doc, document_loader
from ..models.openai_chat import OpenaiChat
from ..models.gptui_basic_services.plugins.conversation_service import ConversationService
from ..gptui_kernel.manager import Manager
from ..utils.my_text import MyText as Text
from ..utils.my_text import MyLines as Lines


gptui_logger = logging.getLogger("gptui_logger")


def preprocess_config_path(config: dict) -> dict:
    """Given a config, normalize its paths and return the config with the normalized paths replaced."""
    config["workpath"] = os.path.expanduser(config["workpath"])
    config["dot_env_path"] = os.path.expanduser(config["dot_env_path"])
    config["conversation_path"] = os.path.expanduser(config["conversation_path"])
    config["directory_tree_path"] = os.path.expanduser(config["directory_tree_path"])
    config["vector_memory_path"] = os.path.expanduser(config["vector_memory_path"])
    config["log_path"] = os.path.expanduser(config["log_path"])
    gptui_path = importlib.resources.files("gptui")
    config["GPTUI_BASIC_SERVICES_PATH"] = os.path.expanduser(config["GPTUI_BASIC_SERVICES_PATH"] or gptui_path / "models" / "gptui_basic_services")
    config["PLUGIN_PATH"] = os.path.expanduser(config["PLUGIN_PATH"] or gptui_path / "plugins")
    config["DEFAULT_PLUGIN_PATH"] = os.path.expanduser(config["DEFAULT_PLUGIN_PATH"] or gptui_path / "plugins" / "DEFAULT_PLUGINS")
    return config


class MainApp(App[str]):

    CSS_PATH="layout.tcss"

    BINDINGS = [
        Binding("escape", "hot_key", "active hot key"),
        Binding("ctrl+q", "exit_main_app", "exit the app"),
        Binding("ctrl+n", "add_conversation", "add a conversation"),
        Binding("ctrl+s", "save_conversation", "save a conversation"),
        Binding("ctrl+r", "delete_conversation", "delete a conversation"),
        Binding("ctrl+o", "new_disposable_chat", "open a disposable chat"),
        Binding("ctrl+t", "change_to_assistant_tube", "change_to_assistant_tube"),
        Binding("ctrl+g", "change_to_file_tube", "change_to_file_tube"),
        Binding("ctrl+p", "change_to_plugins_region", "change_to_plugins_region"),
    ]

    def __init__(self, config_path: str, app_version: str):
        super().__init__()
        self.app_version = app_version
        self.stream_openai = True
        self.common_resources = {}
        self.unique_id = itertools.count(1)                 # start from 1 to avoid possible 0 = False trouble
        # Import config
        try:
            with open(os.path.join(os.path.dirname(__file__), '../.default_config.yml'), "r") as default_config_file:
                self.config = yaml.safe_load(default_config_file)
        except FileNotFoundError:
            self.exit(f"Default config file '.default_config.yml' is not found.")
        try:
            with open(config_path, "r") as config_file:
                config = yaml.safe_load(config_file)
        except FileNotFoundError:
            pass
        else:
            self.config.update(config)
        
        self.config["tui_config"]["status_region_default"] = self.config["tui_config"]["status_region_default"] or f"GPTUI {app_version}"
        self.config = preprocess_config_path(self.config)

        self.workpath = self.config["workpath"]

        self.manager = Manager(self, dot_env_config_path=self.config["dot_env_path"], logger=gptui_logger)
        self.manager_init(self.manager)

        try:
            with open(os.path.join(self.workpath, "_last_app_state.json"), "r") as app_state:
                app_state_dict = json.load(app_state)
        except FileNotFoundError:
            app_state_dict = {}
        conversations_recover = app_state_dict.get("conversations_recover")
        if conversations_recover is not None:
            self.config["tui_config"]["conversations_recover"] = conversations_recover
        
        self.status_region_default = self.config["tui_config"]["status_region_default"]
        #self.qdrant_vector=QdrantVector(vector_size=1536, url=self.config["vector_memory_path"], local=True)
        self.qdrant_queue = queue.Queue()
        self.qdrant_result_dict = {}
        self.qdrant_thread = threading.Thread(target=self.qdrant_write_thread, args=(self.qdrant_queue, self.qdrant_result_dict))
        self.qdrant_ready = threading.Event()
        self.qdrant_thread.start()
        self.app_exited = False # It will be used when exiting from app_init

    def compose(self) -> ComposeResult:
        yield AppStart(self, classes="top_layer")
        with Horizontal():
            with Vertical(id = "text_region"):
                with Horizontal(id = "tabs_region"):
                    with Vertical(classes="dot_display"):
                        yield NoPaddingButton("\ueab5", classes="tab_arrow", id="tab_left")
                        yield Label(Text("1", 'yellow'), id="tabs_num_display")
                    #yield Tabs(Tab("None", id="lqt1"), id="chat_tabs")
                    yield Tabs(id="chat_tabs")
                    with Vertical(classes="dot_display"):
                        yield NoPaddingButton("\ueab6", classes="tab_arrow", id="tab_right")
                        yield Label(Text(u'\u260C', 'green'), id="commander_status_display")
                
                with Horizontal(id="chat_window"):
                    yield MyChatWindow(id="chat_region")
                    yield Static(id="chat_region_scroll_bar")
                
                yield MyFillIn(char=chr(0x2500), id="line_between_chat_status")
                
                yield Static(self.status_region_default, id="status_region")
                
                with ContentSwitcher(id="input_switcher"):
                    yield MyMultiInput(placeholder="message region", id="message_region")
                    yield Container(id="voice_input")
            
            with Vertical(id="middle_bar"):
                with Container(id="tool_bar"):
                    yield Button("+", classes="arrow_button", id="add_conversation")
                    yield Button(">", classes="arrow_button", id="save_conversation")
                    yield Button("<", classes="arrow_button", id="read_conversation")
                    yield Button("-", classes="arrow_button", id="delete_conversation")
                    yield Button("x", classes="arrow_button", id="delete_conversation_file")
                    yield Button("n", classes="arrow_button", id="no_context")
                    yield Button(u"\u21A5", classes="arrow_button", id="import_file_to_tube")
                
                with Container(id="middle_switch_container"):
                    yield SlideSwitch([(Text("C"), "conversation_tree"),
                                       (Text("D"), "directory_tree"),
                                       (Text("A"), "assistant_tube"),
                                       (Text("T"), "file_tube"),
                                       (Text("P"), "plugins_region")], direction="up", id="middle_switch")
                
                yield Button("\u21a3", classes="arrow_button", id="fold_no_text_region")

                yield Button("[underline]?[/]", classes="arrow_button", id="help")
                
                yield Static(id="dash_board")
            
            with Vertical(id="no_text_region"):
                with ContentSwitcher(id="no_text_region_content_switcher"):
                    yield ConversationTree(self.config["conversation_path"], "Conversations:", id="conversation_tree")
                    yield MyDirectoryTree(self.config["directory_tree_path"], self.config["directory_tree_path"], id="directory_tree")
                    yield MyChatWindow(id="assistant_tube")
                    yield Tube(app=self, id="file_tube")
                    with Vertical(id="plugins_region"):
                        with Horizontal():
                            yield Label("Plugins: ", id="plugin_label")
                            yield NoPaddingButton("|Refresh|", id="plugin_refresh")
                        user_plugins_up = GridContent(name="UserPluginsUp", column_num=4, grid_rows="3", classes="user_plugins", id="user_plugins_up") 
                        user_plugins_down = GridContent(name="UserPluginsDown", column_num=4, grid_rows="3", classes="user_plugins", id="user_plugins_down")
                        yield MultiGridContent(grid_list=[user_plugins_up, user_plugins_down], id="plugins_control")
                
                with Horizontal(id="control_region"):
                    yield SlideSwitch(
                        [
                            (Text("I"), "info_display"),
                            (Text("S"), "command_input"),
                        ], id="control_switch", direction="down")
                    with ContentSwitcher(id="control_panel"):
                        yield Label("Chat Parameters", id="info_display")
                        yield MyMultiInput(placeholder="Input command:", id="command_input")
                
                with Horizontal(id="direct_control"):
                    with Horizontal(id="direct_control_switch"):
                        yield Static(Text(" R", "yellow"), classes="switch_label")
                        tui_config = self.config["tui_config"]
                        assert isinstance(tui_config, dict)
                        yield Switch(value=tui_config["conversations_recover"], id="conversations_recover", classes="min_switch")
                        yield Static(Text(" V", "yellow"), classes="switch_label")
                        yield Switch(value=tui_config["voice_switch"], id="voice_switch", classes="min_switch")
                        yield Static(Text(" S", "yellow"), classes="switch_label")
                        yield Switch(value=tui_config["speak_switch"], id="speak_switch", classes="min_switch")
                        yield Static(Text(" F", "yellow"), classes="switch_label")
                        yield Switch(value=tui_config["file_wrap_display"], id="file_wrap_display", classes="min_switch")
                    yield NoPaddingButton("|Exit|", id="exit")
    
    def on_mount(self):
        self.query_one("#no_text_region_content_switcher").current = "conversation_tree"
        self.query_one("#control_panel").current = "info_display"
        self.query_one("#input_switcher").current = "message_region"
        self.query_one("#message_region").focus()

    async def on_ready(self):
        status = await self.app_init()
        if status is False:
            return
        message_region = self.query_one("#message_region")
        message_region.border_title = u'\u2500' * self.query_one("#message_region").content_size.width
        message_region.border_subtitle = u'\u2500' * self.query_one("#message_region").content_size.width
        self.query_one("#control_panel").border_subtitle = "Control Panel"
        assistant_tube = self.query_one("#assistant_tube")
        assistant_tube.border_title = "Assistant Tube"
        assistant_tube.border_subtitle = "[@click=app.assistant_tube_clear]Clear Tube[/]"
        self.no_context_manager = NoContextChat(self)
        # rebuild conversations in last running.
        self.run_worker(self.conversations_display_init(conversation_active=self.openai.conversation_active))
        self.service_init()
        self.query_one("#conversation_tree").conversation_refresh()

    async def on_button_pressed(self, event) -> None:

        if event.button.id == "add_conversation":
            await self.action_add_conversation()
        
        elif event.button.id == "save_conversation":
            await self.action_save_conversation()

        elif event.button.id == "read_conversation":
            await self.action_read_conversation()
        
        elif event.button.id == "delete_conversation":
            await self.action_delete_conversation()
        
        elif event.button.id == "delete_conversation_file":
            await self.action_delete_conversation_file()
        
        elif event.button.id == "no_context":
            await self.action_new_disposable_chat()
        
        elif event.button.id == "tab_left":
            self.query_one("#chat_tabs").action_previous_tab()
        
        elif event.button.id == "tab_right":
            self.query_one("#chat_tabs").action_next_tab()

        elif event.button.id == "fold_no_text_region":
            button = self.query_one("#fold_no_text_region")
            no_text_region = self.query_one("#no_text_region")
            if str(button.label) == "\u21a3":
                no_text_region.add_class("folded")
                button.label = "\u21a2"
            else:
                no_text_region.remove_class("folded")
                button.label = "\u21a3"

        elif event.button.id == "exit":
            await self.action_exit_main_app()
        
        elif event.button.id == "import_file_to_tube":
            file_path = self.query_one("#directory_tree").file_path_now
            try:
                document = document_loader(file_path)
            except TypeError:
                ani_id = uuid.uuid4()
                self.post_message(
                    AnimationRequest(
                        ani_id=ani_id,
                        action="start",
                        ani_type="static",
                        keep_time=3,
                        ani_end_display=self.status_region_default,
                        others=Text("Selected file type is not suppported.", "yellow"),
                    )
                )
                return
            if not document:
                return
            document_metadata = document[0].metadata
            source = document_metadata['source']
            document_name = os.path.basename(source)
            doc_name, doc_ext = os.path.splitext(document_name)
            doc = Doc(doc_name=doc_name, doc_ext=doc_ext, pointer=document[0])
            file_tube = self.query_one("#file_tube")
            file_tube.add_document_to_up_tube(document=doc)
            self.query_one("#middle_switch").change_to_pointer("file_tube")
        
        elif event.button.id == "plugin_refresh":
            self.plugin_refresh()

        elif event.button.id == "help":
            gptui_package_dir = importlib.resources.files("gptui")
            help_path = gptui_package_dir / "help.md"
            help_document = document_loader(help_path)
            self.push_screen(MarkdownPreview(markdown=help_document[0].page_content, previewer_title="Help"))

    async def on_input_submitted(self, message) -> None:
        if message.input.id == "message_region":
            input = message.value
            if self.query_one("#chat_tabs").tab_count == 0:
                self.horse.refresh_input(input)
                return
            upload_file_switch = self.query_one("#file_tube #send_switch")
            tab = self.query_one("#chat_tabs").active_tab
            if not tab:
                Thread(target = self.no_context_manager.chat, args = (input,)).start()
                return
            id = int(tab.id[3:])
            if id <= 0:
                Thread(target = self.no_context_manager.chat, args = (message.value,)).start()
                return
            context = self.openai.conversation_dict[self.openai.conversation_active]["openai_context"]
            stream = context.parameters.get("stream", True)

            if upload_file_switch.value:
                displayer = self.query_one("#status_region")
                tf = TubeFiles(displayer=displayer)
                tube = self.query_one("#file_tube")
                files = tube.get_upload_files()
                prompt = await tf.insert_files(*files, input=input)
                
                if stream:
                    self.chat_stream(prompt, context)
                else:
                    self.chat_thread(prompt, context)
                upload_file_switch.value = False
            
            else:
                if stream:
                    self.chat_stream(input, context)
                else:
                    self.chat_thread(input, context)

        elif message.input.id == "command_input":
            try:
                await self.run_action(message.value)
            except ActionError as e:
                gptui_logger.info(f"ActionError: unable to parse the command: {message.value}")
                ani_id = uuid.uuid4()
                self.post_message(
                    AnimationRequest(
                        ani_id=ani_id,
                        action="start",
                        ani_type="static",
                        keep_time=3,
                        ani_end_display=self.status_region_default,
                        others=Text(f"Unable to parse the command: {message.value}", "yellow"),
                    )
                )

    async def on_voice_submitted(self, message) -> None:
        tab = self.query_one("#chat_tabs").active_tab
        if not tab:
            Thread(target = self.no_context_manager.chat, args = (message.content,)).start()
            return
        id = int(tab.id[3:])
        if id > 0:
            context = self.openai.conversation_dict[self.openai.conversation_active]["openai_context"]
            stream = context.parameters.get("stream", True)
            if stream:
                self.chat_stream(message.content, context)
            else:
                self.chat_thread(message.content, context)
        else:
            Thread(target = self.no_context_manager.chat, args = (message.content,)).start()
    
    def on_my_scroll_support_mixin_my_scroll_changed(self, message) -> None:
        if message.id == "chat_region":
            height = self.query_one("#chat_region_scroll_bar").content_size.height
            content = self.scroll_bar_content(message.my_scroll, height)
            self.query_one("#chat_region_scroll_bar").update(content)

    async def on_slider_slider_changed(self, event) -> None:
        if event.slide_switch.id == "control_switch":
            self.query_one("#control_panel").current = event.slider.pointer
            if event.slider.pointer == "info_display":
                self.chat_parameters_display()
        elif event.slide_switch.id == "middle_switch":
            self.query_one("#no_text_region_content_switcher").current = event.slider.pointer
            # scroll the assistant tube to end
            await asyncio.sleep(0.2) # wait the assistant tube to mount to get the correct width
            if event.slider.pointer == "assistant_tube":
                assistant_tube = self.query_one("#assistant_tube")
                assistant_tube.refresh_content_wrap_request_execute()
                assistant_tube.scroll_to_end(refresh=True)
            elif event.slider.pointer == "plugins_region":
                if self.openai.conversation_active > 0:
                    self.plugin_refresh()
            elif event.slider.pointer == "directory_tree":
                self.query_one("#directory_tree").reload()
            elif event.slider.pointer == "conversation_tree":
                self.query_one("#conversation_tree").conversation_refresh()
    
    async def on_switch_changed(self, event) -> None:
        if event.switch.id == "voice_switch":
            if event.value:
                voice = Voice(self)
                self.query_one("#voice_input").mount(voice)
                self.query_one("#input_switcher").current = "voice_input"
                self.query_one("#speak_switch").value = True
                await asyncio.sleep(0.5)
                self.query_one("Voice").focus()
            else:
                self.query_one("#input_switcher").current = "message_region"
                voice = self.query_one("Voice")
                if voice:
                    voice.remove()
                self.query_one("#speak_switch").value = False
                self.query_one("#message_region").focus()
        elif event.switch.id == "speak_switch":
            if event.value is True:
                self.voice_service.connect()
            else:
                self.voice_service.cancel_speak()
        elif event.switch.id == "file_wrap_display":
            tab_id = self.query_one("#chat_tabs").active
            if not tab_id:
                return
            id = int(tab_id[3:])
            if id > 0:
                self.openai.conversation_active = id
                conv_content = self.openai.conversation_dict[id]["openai_context"].chat_context
                self.context_to_chat_window(conv_content)
            else:
                self.no_context_manager.no_context_chat_active = id
                self.context_to_chat_window(self.no_context_manager.no_context_chat_dict[self.no_context_manager.no_context_chat_active])

    def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
        tab_id = event.tab.id
        id = int(tab_id[3:])
        if id > 0:
            gptui_logger.debug(f"tab: {id}")
            self.openai.conversation_active = id
            openai_context = self.openai.conversation_dict[id]["openai_context"]
            self.context_to_chat_window(openai_context.chat_context)
            tokens_window = self.get_tokens_window(openai_context.parameters.get("model"))
            self.dash_board.dash_board_display(tokens_window, conversation_id=id)
            self.query_one("#status_region").update(self.status_region_default)
            self.query_one("#message_region").focus()
            self.register_plugins_to_manager()
            self.register_default_plugins_to_manager()
            self.plugin_refresh()
            self.chat_parameters_display()
        else:
            self.no_context_manager.no_context_chat_active = id
            self.context_to_chat_window(self.no_context_manager.no_context_chat_dict[self.no_context_manager.no_context_chat_active])
            dashboard = self.query_one("#dash_board")
            height = dashboard.content_size.height
            dashboard.update(Text(" X \n" * height,"red"))
            self.query_one("#status_region").update(Text("Disposable chat now.", "yellow"))
            self.query_one("#message_region").focus()
        tab_num = self.query_one("#chat_tabs").tab_count
        if tab_num > 9:
            tab_num = u'\u21DE'
        self.query_one("#tabs_num_display").update(Text(str(tab_num), 'yellow'))

    async def on_tabs_cleared(self, event: Tabs.Cleared) -> None:
        self.openai.conversation_active = 0
        chat_region = self.query_one("#chat_region")
        chat_region.clear()
        fun_zone = FunZone(chat_region)
        apples = [JustBeing(), BombBoom()]
        apple = random.choice(apples)
        self.horse.set_happy(fun_zone)
        self.run_worker(self.horse.run(apple))

    def on_animation_request(self, message) -> None:
        self.animation_manager.manage(message)

    def on_icon_region_check_box_status_changed(self, event) -> None:
        check_box = event.check_box
        status = event.status
        pointer = check_box.pointer
        if check_box.domain.id in {"user_plugins_up", "user_plugins_down"}:
            if self.openai.conversation_active <= 0:
                ani_id = uuid.uuid4()
                self.post_message(
                    AnimationRequest(
                        ani_id=ani_id,
                        action="start",
                        ani_type="static",
                        keep_time=3,
                        ani_end_display=self.status_region_default,
                        others=Text("There is no conversation currently available for plugins.", "yellow"),
                    )
                )
                return
            context = self.openai.conversation_dict[self.openai.conversation_active]["openai_context"]
            if status is True:
                context.plugins.append(pointer.plugin_info)
                self.manager.add_plugins(pointer.plugin_info)
            if status is False:
                try:
                    context.plugins.remove(pointer.plugin_info)
                except ValueError:
                    gptui_logger.warning("Try to remove a non-existent plugin_info.")
                self.manager.remove_plugins(pointer.plugin_info)

    async def on_resize(self, event) -> None:
        """app resized"""
        self.run_worker(self.message_region_border_reset())

    async def on_my_chat_window_resize(self, event) -> None:
        """MyChatWindow resized"""
        # If this check isn't made here, encountering an error in app_init and exiting might lead to other error messages. These additional errors occur because app_init terminates the program but doesn't immediately stop it. During this peroid, other methods might run without app_init having finished correctly, leading to errors. These additional errors shouldn't be logged upon program exit.
        if self.app_exited is True:
            return
        id = self.openai.conversation_active
        if id == 0:
            return
        openai_context = self.openai.conversation_dict[id]["openai_context"]
        self.context_to_chat_window(openai_context.chat_context)
        self.run_worker(self.message_region_border_reset())

    async def on_common_message(self, message) -> None:
        if message.message_name == "write_file":
            document = message.message_content
            file_tube = self.query_one("#file_tube")
            file_tube.add_document_to_down_tube(document=document)
            self.query_one("#middle_switch").change_to_pointer("file_tube")
        if message.message_name == "vector_memory_write":
            message_content = message.message_content
            self.qdrant_queue.put({"action": "write_reference", "content": message_content})

    def action_set_chat_parameters(self, parameters: dict) -> None:
        # valid check
        if not isinstance(parameters, dict):
            self.query_one("#status_region").update(Text("'parameters' have to be a dict."), "red")
            return

        self.openai.conversation_dict[self.openai.conversation_active]["openai_context"].parameters.update(parameters)
        self.calibrate_chat_parameters(self.openai.conversation_active)
        self.chat_parameters_display()

    def action_set_max_sending_tokens_ratio(self, ratio: float) -> None:
        # valid check
        if not isinstance(ratio, float):
            self.query_one("#status_region").update(Text("'max_sending_tokens_ratio' have to be a flat number."), "red")
            return
        if not 0.0 < ratio < 1.0:
            self.query_one("#status_region").update(Text("'max_sending_tokens_ratio' have to be in range from 0.0 to 1.0."), "red")
            return
        
        self.openai.conversation_dict[self.openai.conversation_active]["max_sending_tokens_ratio"] = ratio
        
        # set max_sending_tokens_num
        openai_context = self.openai.conversation_dict[self.openai.conversation_active]["openai_context"]
        tokens_window = self.config["openai_model_info"][openai_context.parameters["model"]]["tokens_window"]
        openai_context.max_sending_tokens_num = math.floor(ratio * tokens_window)
        # set max_tokens
        openai_context.parameters["max_tokens"] = tokens_window - openai_context.max_sending_tokens_num
    
    def action_copy_code(self, index: int):
        """Action can only be defined within App, Screen, or Widget."""
        self.decorate_display.action_copy_code(index)
    
    def action_assistant_tube_clear(self):
        assistant_tube=self.query_one("#assistant_tube")
        assistant_tube.clear()

    # Shortcut keys ###############################################################################################
    async def action_exit_main_app(self):
        app_state = {"conversations_recover": self.query_one("#conversations_recover").value}
        try:
            with open(os.path.join(self.workpath, "_last_app_state.json"), "w") as write_file:
                write_file.write(json.dumps(app_state, ensure_ascii = False, sort_keys = True, indent = 4, separators = (',',':')))
        except Exception as e:
            state_write_status = False
            gptui_logger.error(f"Write app last state failed. Error: {e}")
        else:
            state_write_status = True
        switch = self.query_one("#conversations_recover")
        if switch.value:
            try:
                conversation_dict = copy.deepcopy(self.openai.conversation_dict)
                conversation_plugins_dict = {}

                # changes openai_context to dict version to write inot filele
                for id in conversation_dict.keys():
                    # Store plugin information separately to avoid issues with plugin information serialization error due to auto init object
                    # Plugins set will be retrieved when load conversations cache in OpenaiChatManage.__init__
                    openai_context_original = conversation_dict[id]["openai_context"]
                    conversation_plugins_dict[id] = [plugin[1] if len(plugin)==2 else plugin[2] for plugin in openai_context_original.plugins]
                    # Clear plugin information to avoid serialization errors; the plugin information has been saved in conversation_plugins_dict
                    openai_context_original.plugins = []
                    openai_context = asdict(openai_context_original)
                    conversation_dict[id]["openai_context"] = openai_context
                content = {"conversation_active": self.openai.conversation_active, "conversation_dict": conversation_dict, "conversation_plugins_dict": conversation_plugins_dict}
                with open(os.path.join(self.openai.workpath, "_conversations_cache.json"), "w") as write_file:
                    write_file.write(json.dumps(content, ensure_ascii = False, sort_keys = True, indent = 4, separators = (',',':')))

                # cache vector memory
                self.query_one("#status_region").update("Caching conversation vectors ...")
                await asyncio.sleep(0.1)
                collections = self.openai.conversation_dict.keys()
                cache_event = threading.Event()
                for collection in collections:
                    self.qdrant_queue.put(
                        {
                            "action": "collection_cache",
                            "content":{
                                "collection_name": str(collection),
                                "event": cache_event,
                            },
                        }
                    )
                    cache_event.wait()
                    cache_event.clear()
                self.query_one("#status_region").update(Text("Conversation vectors cached.", "green"))
                await asyncio.sleep(0.1)
            
            except Exception as e:
                if state_write_status:
                    self.run_worker(self.exit_check("Conversation tabs is not saved successfully, do you want to exit without save?"))
                else:
                    self.run_worker(self.exit_check("Conversation tabs and app state are not saved successfully, do you want to exit without save?"))
                gptui_logger.error(f"Save conversation tabs failed. Error: {e}")
            else:
                if state_write_status:
                    self.qdrant_queue.put({"action": "STOP"})
                    self.qdrant_thread.join()
                    self.exit("Conversation is cached successfully.")
                else:
                    self.run_worker(self.exit_check("App state is not saved successfully, do you want to exit without save?"))
        else:
            if state_write_status:
                self.qdrant_queue.put({"action": "STOP"})
                self.qdrant_thread.join()
                self.exit("App's last state was saved successfully.")
            else:
                self.run_worker(self.exit_check("App state is not saved successfully, do you want to exit without save?"))

    async def action_add_conversation(self):
        await self.horse.stop_async()
        conversation_id = self.openai.open_conversation_with_mode()
        self.openai.conversation_active = conversation_id
        tab_id = "lqt" + str(conversation_id)
        tab_name = self.openai.conversation_dict[self.openai.conversation_active]["tab_name"]
        chat_tabs = self.query_one("#chat_tabs")
        chat_tabs.add_tab(Tab(tab_name, id=tab_id))
        await asyncio.sleep(0.2)
        chat_tabs.active = tab_id
        chat_tabs._scroll_active_tab()
        self.context_to_chat_window(self.openai.conversation_dict[self.openai.conversation_active]["openai_context"].chat_context)

    async def action_save_conversation(self):
        conversation_id = self.openai.conversation_active
        # Check if is there a conversation.
        if not conversation_id:
            ani_id = uuid.uuid4()
            self.post_message(
                AnimationRequest(
                    ani_id=ani_id,
                    action="start",
                    ani_type="static",
                    keep_time=3,
                    ani_end_display=self.status_region_default,
                    others=Text("Conversations are cleared.", "yellow"),
                )
            )
            return
        status = await self.openai.write_conversation(conversation_id)
        if status is not True:
            return
        collection = self.openai.conversation_active
        self.qdrant_queue.put(
            {
                "action": "collection_save",
                "content":{
                    "collection_name": str(collection),
                    "event": None,
                },
            }
        )

    async def action_delete_conversation(self):
        if self.query_one("#chat_tabs").tab_count == 0:
            return
        self.run_worker(self.delete_conversation_check())

    async def action_new_disposable_chat(self):
        no_context_chat_id = self.no_context_manager.open_no_context_chat()
        self.no_context_manager.no_context_chat_active = no_context_chat_id
        tab_id = "lqt" + str(no_context_chat_id)
        self.query_one("#chat_tabs").add_tab(Tab("NoCo", id=tab_id))
        await asyncio.sleep(0.2)
        self.query_one("#chat_tabs").active = tab_id
        self.context_to_chat_window([])

    async def action_read_conversation(self):
        conversation_file_now = self.query_one("#conversation_tree").file_path_now
        if conversation_file_now:
            status, info = self.openai.read_conversation(str(conversation_file_now))
            if status is False:
                if isinstance(info, int):
                    # The conversation already exits, switch to that conversation
                    self.query_one("#chat_tabs").active = "lqt" + str(info)
                    return
                else:
                    return
            self.context_to_chat_window(self.openai.conversation_dict[self.openai.conversation_active]["openai_context"].chat_context)
            tab_name = self.openai.conversation_dict[self.openai.conversation_active]["tab_name"]
            tab_id = str(self.openai.conversation_active)
            tab_id = "lqt" + tab_id
            self.query_one("#chat_tabs").add_tab(Tab(tab_name, id=tab_id))
            await asyncio.sleep(0.2)
            self.query_one("#chat_tabs").active = tab_id
        else:
            self.query_one("#status_region").update(Text("No conversation selected.", "yellow"))

    async def action_delete_conversation_file(self):
        conversation_tree = self.query_one("#conversation_tree")
        if self.query_one("#middle_switch").index != 0:
            ani_id = uuid.uuid4()
            self.post_message(
                AnimationRequest(
                    ani_id=ani_id,
                    action="start",
                    ani_type="static",
                    keep_time=3,
                    ani_end_display=self.status_region_default,
                    others=Text("Only conversation files can be deleted. Switch to the conversation list first.", "yellow"),
                )
            )
            return

        file_path = conversation_tree.file_path_now
        if not file_path:
            ani_id = uuid.uuid4()
            self.post_message(
                AnimationRequest(
                    ani_id=ani_id,
                    action="start",
                    ani_type="static",
                    keep_time=3,
                    ani_end_display=self.status_region_default,
                    others=Text("No conversation is selected.", "yellow"),
                )
            )
            return
        
        def check_dialog_handle(confirm: bool) -> None:
            if confirm:
                try:
                    os.remove(file_path)
                except FileNotFoundError:
                    ani_id = uuid.uuid4()
                    self.post_message(
                        AnimationRequest(
                            ani_id=ani_id,
                            action="start",
                            ani_type="static",
                            keep_time=3,
                            ani_end_display=self.status_region_default,
                            others=Text("The conversation selected does not exist", "red"),
                        )
                    )
                except Exception as e:
                    ani_id = uuid.uuid4()
                    self.post_message(
                        AnimationRequest(
                            ani_id=ani_id,
                            action="start",
                            ani_type="static",
                            keep_time=3,
                            ani_end_display=self.status_region_default,
                            others=Text(f"An error occurred while deleting conversation file: {e}", "red"),
                        )
                    )
                else:
                    conversation_tree.conversation_refresh()
            else:
                return

        self.push_screen(
            CheckDialog(
                prompt=Text("Are you sure you want to delete this conversation file?\nNote: Once deleted, it cannot be recovered.", "yellow")),
            check_dialog_handle,
        )

    def action_change_to_assistant_tube(self):
        self.query_one("#middle_switch").change_to_pointer("assistant_tube")
    
    def action_change_to_file_tube(self):
        self.query_one("#middle_switch").change_to_pointer("file_tube")

    def action_change_to_plugins_region(self):
        self.query_one("#middle_switch").change_to_pointer("plugins_region")
    
    def action_hot_key(self):
        hot_key_display = Text(
            textwrap.dedent(
            """
            | n -> new chat            w -> save chat           l -> load chat       |
            | r -> remove chat         x -> delete chat file    o -> disposable chat |
            | c -> conversation_tree   d -> directory_tree      a -> assistant_tube  |
            | t -> file_tube           p -> plugins_region      i -> info_display    |
            | s -> command_input       9 -> left chat           0 -> right chat      |
            | f -> focus conversation  h -> help                z -> file_wrap       |
            | k -> toggle speak        v -> toggle voice        q -> return          |
            | m -> focus input                                                       |
            """
            )
        )
        self.push_screen(HotKey(hot_key_display), self.hot_key_handle)

    async def hot_key_handle(self, key: str):
        if key == "n":
            await self.action_add_conversation()
        elif key == "w":
            await self.action_save_conversation()
        elif key == "l":
            await self.action_read_conversation()
        elif key == "r":
            await self.action_delete_conversation()
        elif key == "x":
            await self.action_delete_conversation_file()
        elif key == "o":
            await self.action_new_disposable_chat()
        elif key == "c":
            self.query_one("#middle_switch").change_to_pointer("conversation_tree")
        elif key == "d":
            self.query_one("#middle_switch").change_to_pointer("directory_tree")
        elif key == "a":
            self.query_one("#middle_switch").change_to_pointer("assistant_tube")
        elif key == "t":
            self.query_one("#middle_switch").change_to_pointer("file_tube")
        elif key == "p":
            self.query_one("#middle_switch").change_to_pointer("plugins_region")
        elif key == "i":
            self.query_one("#control_switch").change_to_pointer("info_display")
        elif key == "s":
            self.query_one("#control_switch").change_to_pointer("command_input")
            self.query_one("#command_input").focus()
        elif key == "9":
            self.query_one("#chat_tabs").action_previous_tab()
        elif key == "0":
            self.query_one("#chat_tabs").action_next_tab()
        elif key == "f":
            self.query_one("#middle_switch").change_to_pointer("conversation_tree")
            self.query_one("#conversation_tree").focus()
        elif key == "h":
            self.query_one("#help").press()
        elif key == "z":
            self.query_one("#file_wrap_display").toggle()
        elif key == "k":
            self.query_one("#speak_switch").toggle()
        elif key == "v":
            self.query_one("#voice_switch").toggle()
        elif key == "m":
            self.query_one("#message_region").focus()

    ###############################################################################################################

    def calibrate_chat_parameters(self, conversation_id: int | None = None):
        conversation_id = conversation_id or self.openai.conversation_active
        conversation = self.openai.conversation_dict[conversation_id]
        # set max_sending_tokens_num
        ratio = conversation["max_sending_tokens_ratio"]
        openai_context = conversation["openai_context"]
        tokens_window = self.config["openai_model_info"][openai_context.parameters["model"]]["tokens_window"]
        openai_context.max_sending_tokens_num = math.floor(ratio * tokens_window)
        # set max_tokens
        openai_context.parameters["max_tokens"] = tokens_window - openai_context.max_sending_tokens_num

    def chat_parameters_display(self) -> None:
        context_parameters = self.openai.conversation_dict[self.openai.conversation_active]["openai_context"].parameters
        display = ""
        for key, value in context_parameters.items():
            display += f"{key}: {value}\n"
        display += f"max_sending_tokens_ratio: {self.openai.conversation_dict[self.openai.conversation_active]['max_sending_tokens_ratio']}"
        self.query_one("#info_display").update(display)
    
    def tab_rename(self, tab: Tab, name: Text | str) -> None:
        tab.label = Text.from_markup(name) if isinstance(name, str) else name
        tab.update(name)
        underline = self.query_one("#chat_tabs").query_one(Underline)
        tab_name_length = Text(tab.label_text).cell_len
        underline.highlight_end = underline.highlight_start + tab_name_length

    class ChatThread(Thread):
        def __init__(self, app, input: str, context: OpenaiContext) -> None:
            super().__init__()
            self.app = app
            self.input = input
            self.context = context

        def run(self) -> None:
            piece = {"role":"user", "content":self.input}
            self.app.context_piece_to_chat_window(piece, change_line=True, decorator_switch=True)
            self.app.openai.openai_chat.chat(message=piece, context=self.context)
            self.app.conversation_tab_rename(self.context)

    def chat_thread(self, input_text: str, context: OpenaiContext):
        thread_chat = self.ChatThread(self, input_text, context)
        thread_chat.start()

    @work(exclusive=True, thread=True)
    def chat_stream(self, input_text: str, context: OpenaiContext) -> None:
        piece = {"role":"user", "content":input_text}
        self.context_piece_to_chat_window(piece, change_line=True, decorator_switch=True)
        self.openai.openai_chat.chat_stream(message=piece, context=context)
        self.conversation_tab_rename(context)

    def conversation_tab_rename(self, context: OpenaiContext):
        conversation_id = context.id
        tab_id = "lqt" + str(conversation_id)
        tab = self.query_one(f"#chat_tabs #{tab_id}")
        tokens_num = context.tokens_num
        assert tokens_num is not None
        if (tab.label_text == "None" or tab.label_text == "New") and tokens_num >= 200:
            self.query_one("#status_region").update("Conversation renaming...")
            try:
                rename_function = self.manager.services.sk_kernel.skills.get_function("conversation_service", "conversation_title")
                conversation = context.chat_context
                conversation_str = json.dumps(conversation, ensure_ascii = False, sort_keys = True, indent = 4, separators = (',',':'))
                name = str(rename_function(conversation_str))
                name = name.replace("\n", "") # '\n' may cause tab name display error, because tab have only one line.
            except Exception as e:
                self.query_one("#status_region").update(Text("Rename error: " + type(e).__name__,'yellow'))
                gptui_logger.info("Rename failed.")
            else:
                self.openai.conversation_dict[conversation_id]["tab_name"] = name
                self.tab_rename(tab, name)
                self.query_one("#status_region").update(self.status_region_default)
    
    def scroll_bar_content(self, scroll, height):
        y_start = math.floor(scroll.y_start * height)
        y_end = math.ceil(scroll.y_end * height)
        if scroll.y_start == 0 and scroll.y_end == 1:
            content = Text()
        else:
            content = Text()
            content.append_text(Text(u'\u00b7\n'*y_start, 'yellow'))
            content.append_text(Text('-\n'*(y_end-y_start), 'blue'))
            content.append_text(Text(u'\u00b7\n'*(height-y_end), 'yellow'))
        return content

    # context to chat window
    ############################################################################## context to chat window
    def context_to_chat_window(self, context:list[dict], change_line:bool=True) -> None:
        self.query_one("#chat_region").clear()
        self.decorate_display.clear_code_block() # clear code_block DecorateDisplay
        for piece in context:
            piece_content = {"role":piece["role"], "content":piece["content"]}
            self.context_piece_to_chat_window(piece=piece_content, change_line=change_line, decorator_switch=True)

    def context_piece_to_chat_window(self, piece: dict, change_line: bool = False, decorator_switch: bool = False) -> None:
        chat_region = self.query_one("#chat_region")
        piece = self.filter(piece)
        if piece:
            if decorator_switch:
                out = self.decorator(piece)
                chat_region.write_lines(out)
                if change_line:
                    chat_region.write_lines([Text()])
            else:
                out = piece["content"] + '\n'
                chat_region.write(Text(out))
                if change_line:
                    chat_region.write(Text('\n'))
    ############################################################################## context to chat window
    
    # display assistant's talk in assistant_tube 
    def context_piece_to_assistant_tube(self, piece: dict) -> None:
        display = self.query_one("#assistant_tube")
        if piece["content"].endswith('\n'):
            end = '\n'
        else:
            end = '\n\n'
        if piece["role"] == "assistant_app":
            chat_content = Text.from_markup("[black on white]Assistant:[/]\n") + Text(piece["content"] + end, "yellow")
        elif piece["role"] == "gpt":
            chat_content = Text.from_markup("[black on white]GPT:[/]\n") + Text(piece["content"] + end, "green")
        elif piece["role"] == "function":
            name = piece["name"]
            chat_content = Text.from_markup("[black on white]Function:[/]") + Text.from_markup(f"[bold blue] {name}[/]\n") + Text(piece["content"] + end, "yellow")
        elif piece["role"] == "other":
            chat_content = Text.from_markup("[black on white]Other from gpt:[/]\n") + Text(piece["content"] + end, "red")
        else:
            chat_content = None
        if chat_content is not None:
            if self.query_one("#no_text_region_content_switcher").current == "assistant_tube":
                display.write(chat_content)
            else:
                display.write_content_without_display(chat_content)

    def filter(self, piece: dict) -> dict | None:
        role = piece["role"]
        if role == "user":
            return piece
        elif role == "assistant":
            if not piece["content"].startswith("<log />"):
                return piece
            else:
                return None
        else:
            return None

    def decorator(self, piece: dict, stream: bool = False, copy_code: bool = True, emoji: bool = True) -> Lines:
        content = piece["content"]
        role = piece["role"]
        if role == "user":
            color = "green"
        elif role == "assistant":
            color = "red"
        elif role == "system":
            color = "yellow"
        else:
            color = "white"
        displayer = self.query_one("#chat_region")
        width = displayer.content_size.width
        if emoji:
            content = Emoji.replace(content)
        wrap_file = self.query_one("#file_wrap_display").value
        out = self.decorate_display.pre_wrap_and_highlight(
            input_string=content,
            stream=stream,
            copy_code=copy_code,
            wrap={"file_wrap":{"wrap": wrap_file, "wrap_num": 4}})
        out = self.decorate_display.background_chain(out, width-5)
        out, _, _ = self.decorate_display.panel_chain(*out, panel_color=color)
        out = self.decorate_display.indicator_chain(out, indicator_color=color)
        return out
    
    def get_tokens_window(self, model: str) -> int:
        """
        Query tokens window for openai model from config.
        Return 0 if no corresponding tokens window for model in config.
        """
        model_info = self.config["openai_model_info"].get(model)
        if model_info is None:
            return 0
        else:
            return model_info.get("tokens_window") or 0
    
    async def delete_conversation_check(self) -> None:
        tabs = self.query_one("#chat_tabs")
        old_tab_id = tabs.active_tab.id
        if int(old_tab_id[3:]) < 0:
            tabs.remove_tab(old_tab_id)
            self.no_context_manager.no_context_chat_delete(int(old_tab_id[3:]))
            return

        def check_dialog_handle(confirm: bool) -> None:
            if confirm:
                tabs.remove_tab(old_tab_id)
                self.openai.conversation_delete(conversation_id=int(old_tab_id[3:]))
            else:
                return

        self.push_screen(CheckDialog(prompt="Are you sure to close this conversation?\nUnsaved conversations will not be saved."), check_dialog_handle)

    async def exit_check(self, prompt: Text|str) -> None:
        def check_dialog_handle(confirm: bool) -> None:
            if confirm:
                self.qdrant_queue.put({"action": "STOP"})
                self.qdrant_thread.join()
                self.exit()
            else:
                return
        self.push_screen(CheckDialog(prompt=prompt), check_dialog_handle)
    
    async def message_region_border_reset(self) -> None:
        """Refresh the border display of the message_region"""
        message_region = self.query_one("#message_region")
        message_region_width = message_region.content_size.width
        message_region.border_title = u'\u2500' * message_region_width
        message_region.border_subtitle = u'\u2500' * message_region_width

    async def conversations_display_init(self, conversation_active: int):
        """
        "conversation_active" needs to be passed in, because it may be changed during the execution of this function.
        """
        if conversation_active == 0:
            return
        conversation_dict = self.openai.conversation_dict
        chat_tabs = self.query_one("#chat_tabs")
        for key, value in conversation_dict.items():
            tab_id = "lqt" + str(key)
            tab_name = value["tab_name"]
            chat_tabs.add_tab(Tab(tab_name, id = tab_id))
        await asyncio.sleep(0.2)
        chat_tabs.active = "lqt" + str(conversation_active)
    
    def register_plugins_to_manager(self):
        plugins_list = self.openai.conversation_dict[self.openai.conversation_active]["openai_context"].plugins
        self.manager.overwrite_plugins(plugins_list)
        
    def register_default_plugins_to_manager(self):
        semantic_plugins_list, native_plugins_list = self.manager.scan_plugins(self.config["DEFAULT_PLUGIN_PATH"])
        for plugin in semantic_plugins_list:
            self.manager.add_plugins(plugin.plugin_info)
        for plugin in native_plugins_list:
            self.manager.add_plugins(plugin.plugin_info)

    def plugin_refresh(self):
        semantic_plugins_list, native_plugins_list = self.manager.scan_plugins(self.config["PLUGIN_PATH"])
        plugin_display_up = self.query_one("#user_plugins_up")
        plugin_display_up.clear()
        plugin_display_down = self.query_one("#user_plugins_down")
        plugin_display_down.clear()
        plugins_actived = self.openai.conversation_dict[self.openai.conversation_active]["openai_context"].plugins
        for plugin in native_plugins_list:
            if plugin.plugin_info[2] in self.config["user_plugins_up"]:
                plugin_display_up.add_children(MyCheckBox(status=(plugin.plugin_info in plugins_actived), icon=Text("  \U000F0880 ", "blue"), label=Text(plugin.name), pointer=plugin, domain=plugin_display_up))
            else:
                plugin_display_down.add_children(MyCheckBox(status=(plugin.plugin_info in plugins_actived), icon=Text("  \U000F0880 ", "blue"), label=Text(plugin.name), pointer=plugin, domain=plugin_display_down))
        for plugin in semantic_plugins_list:
            if plugin.plugin_info[1] in self.config["user_plugins_up"]:
                plugin_display_up.add_children(MyCheckBox(status=(plugin.plugin_info in plugins_actived), icon=Text("  \U000F0C23 ", "purple"), label=Text(plugin.name), pointer=plugin, domain=plugin_display_up))
            else:
                plugin_display_down.add_children(MyCheckBox(status=(plugin.plugin_info in plugins_actived), icon=Text("  \U000F0C23 ", "purple"), label=Text(plugin.name), pointer=plugin, domain=plugin_display_down))
    
    def manager_init(self, manager: Manager) -> None:
        manager.load_services(where=ConversationService(manager), skill_name="conversation_service")
        # The purpose of using the following manually constructed relative import is to 
        # avoid duplicate imports and errors in package identity determination caused by inconsistent package names.
        current_package = __package__
        parent_package = ".".join(current_package.split(".")[:-1])
        manager.register_jobs(module_name=f"{parent_package}.models.jobs")
        manager.register_handlers(module_name=f"{parent_package}.models.handlers")

    def service_init(self) -> None:
        self.animation_manager = AnimationManager(
            displayer={"default":self.query_one("#status_region")},
            ani_links={"default": DefaultAnimation, "static": StaticDisplayAnimation, "setting_memory": SettingMemoryAnimation},
            ani_end_display=self.status_region_default,
        )
        self.decorate_display = DecorateDisplay(self)
        self.drivers = DriverManager(self)
        self.chat_display = ChatResponse(self)
        self.voice_service = VoiceService(self, self.query_one("#speak_switch").value)
        self.notification = Notification(self)
        self.chat_context = ChatContext(self)
        self.assistant_tube = AssistantTube(self)
        self.dash_board = DashBoard(self)
        self.horse = Horse()

    async def app_init(self):
        app_start = self.query_one("AppStart")
        app_start_log = app_start.get_rich_log()
        app_start_func = self.app_init_process(app_start_log)
        app_start.set_init_func(app_start_func)
        status = await app_start.app_init()
        self.app_exited = not status
        return status
    
    async def app_init_process(self, init_log: RichLog) -> bool:
        end_status = False
        init_log.write("Import tiktoken ...")
        await asyncio.sleep(0.01)
        try:
            import tiktoken
        except Exception as e:
            init_log.write(Text(f"An error occurred during the import of tiktoken. Error: {e}", "red"))
            gptui_logger.error(f"An error occurred during the import of tiktoken. Error: {e}")
            await asyncio.sleep(0.1)
            await self.start_failed_exit(init_log, f"An error occurred during the import of tiktoken. Error: {e}")
            end_status = True
        else:
            init_log.write(Text("Import tiktoken done.", "green"))
            await asyncio.sleep(0.01)
        
        if end_status is True:
            # The 'return' is to prevent the statements below from being executed, because App.exit() does not exit immediately.
            return False
        init_log.write("Setting up the OpenAI service ...")
        await asyncio.sleep(0.01)
        try:
            self.openai = OpenaiChatManage(
                app=self,
                manager=self.manager,
                openai_chat=OpenaiChat(self.manager),
                workpath=self.config["conversation_path"],
                conversations_recover=self.query_one("#conversations_recover").value,
            )
        except Exception as e:
            init_log.write(Text(f"An error occurred during setting up the OpenAI service. Error: {e}", "red"))
            gptui_logger.error(f"An error occurred during setting up the OpenAI service. Error: {e}")
            await asyncio.sleep(0.1)
            await self.start_failed_exit(init_log, f"An error occurred during setting up the OpenAI service. Error: {e}")
            end_status = True
        else:
            init_log.write(Text("The OpenAI service is ready.", "green"))
            await asyncio.sleep(0.01)
        
        if end_status is True:
            # The 'return' is to prevent the statements below from being executed, because App.exit() does not exit immediately.
            return False
        init_log.write("Preparing the Qdrant vector database ...")
        await asyncio.sleep(0.01)
        init_log.write("Waiting for the Qdrant service to be ready ...")
        await asyncio.sleep(0.01)

        self.qdrant_ready.wait()
        init_log.write(Text("Qdrant service is ready.", "green"))
        await asyncio.sleep(0.01)
        
        init_log.write("Clean Qdrant collections ...")
        await asyncio.sleep(0.01)
        try:
            # Retrieve all saved conversations
            conversations_ids = self._get_conversations_ids()
            # Retrieve the cached conversations
            try:
                file_path = os.path.join(self.config["conversation_path"], "_conversations_cache.json")
                with open(file_path, "r") as cache_file:
                    conversation_cached = json.load(cache_file)
                    cached_conversation_dict = conversation_cached["conversation_dict"]
                conversations_ids.update(cached_conversation_dict.keys())
            except:
                pass

            collections = await self.qdrant_vector.get_collections_async()
            for collection in collections[::-1]:
                if collection not in conversations_ids:
                    self.qdrant_queue.put(
                        {
                            "action": "delete_collection",
                            "content": {
                                "collection_name": collection,
                            },
                        }
                    )
                    collections.remove(collection)
        except Exception as e:
            init_log.write(Text(f"An error occurred during cleaning collections. Error: {e}", "red"))
            gptui_logger.error(f"An error occurred during cleaning collections. Error: {e}")
            await asyncio.sleep(1)
        else:
            init_log.write(Text("Qdrant vector is clean.", "green"))
            await asyncio.sleep(0.1)
        
        try:    
            init_log.write("Clean conversation ...")
            await asyncio.sleep(0.1)
            event = threading.Event()
            for collection in collections:
                self.qdrant_queue.put(
                    {
                        "action": "collection_clean",
                        "content": {
                                "collection_name": collection,
                                "event": event,
                        },
                    }
                )
                event.wait()
                event.clear()
        except Exception as e:
            init_log.write(Text(f"An error occurred during cleaning conversations. Error: {e}", "red"))
            gptui_logger.error(f"An error occurred during cleaning conversations. Error: {e}")
            await asyncio.sleep(1)
        else:
            init_log.write(Text("Qdrant is ready.", "green"))
            await asyncio.sleep(0.1)

        return True

    def _get_conversations_ids(self, conversation_path: str | None = None) -> set:
        conversation_path = conversation_path or self.config["conversation_path"]
        ids = set()
        try:
            for filename in os.listdir(conversation_path):
                if filename.endswith(".json"):
                    with open(os.path.join(conversation_path, filename), 'r') as file:
                        data = json.load(file)
                        ids.update(data.keys())
        except FileNotFoundError:
            pass
        return ids

    def qdrant_write_thread(self, write_queue, result_dict):
        self.qdrant_vector=QdrantVector(vector_size=1536, url=self.config["vector_memory_path"], local=True)

        async def qdrant_handle(write_queue):
            while True:
                request = write_queue.get()
                assert isinstance(request, dict)
                
                if request["action"] == "STOP":
                    gptui_logger.info("Qdrant thread received 'STOP' action.")
                    break

                elif request["action"] == "write_reference":
                    message_content = request["content"]
                    messages_list = message_content["messages_list"]
                    context_id = message_content["context_id"]
                    memory = self.manager.services.sk_kernel.memory
                    try:
                        for message in messages_list:
                            await memory.save_reference_async(
                                collection = str(context_id),
                                description = repr(message),
                                text = message["content"],
                                external_id = repr(message),
                                external_source_name = "chat_context"
                            )
                    except Exception as e:
                        # Put the unstored information back for future continuation.
                        gptui_logger.error(f"Error occured when save reference to vector memory. Error: {e}")
                        self.chat_context.chat_context_to_vectorize_buffer[id] = messages_list

                elif request["action"] == "collection_clean":
                    collection_name = request["content"]["collection_name"]
                    event = request["content"]["event"]
                    await self.qdrant_vector.collection_clean(collection_name=collection_name)
                    event.set()

                elif request["action"] == "collection_cache":
                    collection_name = request["content"]["collection_name"]
                    event = request["content"]["event"]
                    try:
                        await self.qdrant_vector.collection_cache(collection_name=collection_name)
                    except ValueError as e:
                        gptui_logger.warning(f"Error occurred when cache vector collection. Have no collection named {collection_name}. Error: {e}")
                        self.query_one("#status_region").update(Text(f"Have no collection named {collection_name}. Error: {e}", "yellow"))
                    else:
                        self.query_one("#status_region").update(Text("Conversation vectors cached successfully.", "green"))
                    finally:
                        if event is not None:
                            event.set()
                
                elif request["action"] == "collection_save":
                    collection_name = request["content"]["collection_name"]
                    event = request["content"]["event"]
                    try:
                        await self.qdrant_vector.collection_save(collection_name=collection_name)
                    except ValueError as e:
                        gptui_logger.warning(f"Error occurred when save vector collection. Have no collection named {collection_name}. Error: {e}")
                        self.query_one("#status_region").update(Text(f"Have no collection named {collection_name}. Error: {e}", "yellow"))
                    else:
                        self.query_one("#status_region").update(Text("Conversation vectors saved successfully.", "green"))
                    finally:
                        if event is not None:
                            event.set()
                
                elif request["action"] == "delete_collection":
                    collection_name = request["content"]["collection_name"]
                    await self.qdrant_vector.delete_collection_async(collection_name=collection_name)

        self.qdrant_ready.set()

        asyncio.run(qdrant_handle(write_queue))
        gptui_logger.info("Qdrant thread has closed.")

    async def start_failed_exit(self, init_log: RichLog, exit_log: str):
        self.qdrant_queue.put({"action": "STOP"})
        init_log.write(Text("Please check the log and try restarting later. The system will automatically shut down in three seconds", "red"))
        await asyncio.sleep(1)
        init_log.write(Text("3", "red"))
        await asyncio.sleep(1)
        init_log.write(Text("2", "red"))
        await asyncio.sleep(1)
        init_log.write(Text("1", "red"))
        self.qdrant_thread.join()
        self.exit(exit_log)


class MyDirectoryTree(DirectoryTree):
    def __init__(self, root_path: str, *args, **kwargs):
        self.root_path = root_path
        self.file_path_now = self.root_path
        super().__init__(*args, **kwargs)

    def on_directory_tree_file_selected(self, event) -> None:
        self.file_path_now = event.path

    def on_directory_tree_directory_selected(self, event) -> None:
        self.file_path_now = event.path
        if str(event.path) == self.root_path:
            self.reload()


class ConversationTree(Tree):
    def __init__(self, conversation_path: str, *args, **kwargs):
        self.conversation_path = conversation_path
        super().__init__(*args, **kwargs)
        
    @property
    def file_path_now(self):
        if self.cursor_node:
            return self.cursor_node.data
        else:
            return None

    def on_tree_node_selected(self, event):
        if event.node is self.root:
            self.conversation_refresh()
    
    def conversation_refresh(self):
        self.clear()
        self.root.expand()
        conversation_path = self.conversation_path
        try:
            for filename in os.listdir(conversation_path):
                if filename.endswith(".json") and (filename != "_conversations_cache.json"):
                    self.root.add_leaf(f"{filename}", data=os.path.join(conversation_path, filename))
        except FileNotFoundError:
            pass


class NoContextChat:
    """
    no context chat manager
    {no_context_chat_id:[{"role":role,"content":content}]}
    """
    def __init__(self, app) -> None:
        self.app = app
        self.count = 0
        self.no_context_chat_active = 0
        self.no_context_chat_dict = {}
        self.chat_stream_content = {"role":"assistant", "content":''}
        self.decorate_chat_stream_content_lines = Lines()

    def open_no_context_chat(self) -> int:
        self.count -= 1
        self.no_context_chat_dict[self.count] = []
        return self.count

    def no_context_chat_delete(self, id: int) -> None:
        del self.no_context_chat_dict[id]

    def chat(self, prompt: str) -> None:
        "chat function with openai"
        app = self.app
        message = {"role":"user","content":prompt}
        app.context_piece_to_chat_window(message, change_line=True, decorator_switch=True)
        # manage context just for displaying when refresh
        self.no_context_chat_dict[self.no_context_chat_active].append(message)
        ani_id = str(uuid.uuid4())
        app.post_message(AnimationRequest(ani_id=ani_id, action="start"))
        try:
            response = openai_api().ChatCompletion.create(
                model = app.config["default_openai_parameters"]["model"] or "gpt-4",
                messages = [message],
                stream = app.config["default_openai_parameters"]["stream"],
                )
        except Exception as e:
            app.post_message(AnimationRequest(ani_id=ani_id, action="end"))
            self.app.query_one("#status_region").update(Text(f"An error occurred during communication with OpenAI. Error: {e}"))
            return
        if app.stream_openai:
            i = 0
            collected_messages = ''
            for chunk in response:
                i += 1
                if i == 1:
                    app.post_message(AnimationRequest(ani_id = ani_id, action = "end"))
                    continue
                if chunk.choices[0].finish_reason == "stop":
                    break
                elif chunk.choices[0].finish_reason == "length":
                    app.query_one("#status_region").update(Text("Response exceeds tokens limit", "red"))
                    break
                elif chunk.choices[0].finish_reason == "content_filter":
                    app.query_one("#status_region").update(Text("Omitted content due to a flag from our content filters", "red"))
                    continue
                chunk_message = chunk['choices'][0]['delta']['content']
                collected_messages += chunk_message
                self.chat_stream_display({"message":chunk_message, "status":"content"})
            self.chat_stream_display({"message":'', "status":"end"})
            self.voice_speak(collected_messages)
            self.no_context_chat_dict[self.no_context_chat_active].append({"role":"assistant", "content":collected_messages})
        else:
            app.post_message(AnimationRequest(ani_id = ani_id, action = "end"))
            reply_content = response.choices[0].message.content
            self.voice_speak(reply_content)
            piece = {"role":"assistant", "content":reply_content}
            app.context_piece_to_chat_window(piece=piece, change_line=True, decorator_switch=True)
            self.no_context_chat_dict[self.no_context_chat_active].append({"role":"assistant", "content":reply_content})
    
    def chat_stream_display(self, message: dict, stream: bool = True, copy_code: bool = False) -> None:
        "handle the stream display problems in chat_stream function"
        chat_region = self.app.query_one("#chat_region")
        char = message["message"]
        if message['status'] == "content":
            length = len(self.decorate_chat_stream_content_lines)
            chat_region.right_pop_lines(length, refresh=False)
            self.chat_stream_content["content"] += char
            self.decorate_chat_stream_content_lines = self.app.decorator(self.chat_stream_content, stream, copy_code)
            chat_region.write_lines(self.decorate_chat_stream_content_lines)
        elif message['status'] == "end":
            self.chat_stream_display({"message":'', "status":"content"}, stream=False, copy_code=True)
            chat_region.write_lines([Text()])
            self.chat_stream_content = {"role":"assistant", "content":''}
            self.decorate_chat_stream_content_lines = Lines()

    def voice_speak(self, speak_text: str):
        if self.app.query_one("#speak_switch").value:
            subprocess.Popen(['termux-tts-speak', speak_text])
