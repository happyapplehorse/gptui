from __future__ import annotations
import asyncio
import copy
import hashlib
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
from textual.screen import Screen
from textual.widgets import (
    Static,
    Label,
    Button,
    Tabs,
    Tab,
    ContentSwitcher,
    Switch,
    RichLog,
)
from textual.widgets._tabs import Underline

from .animation import AnimationManager, AnimationRequest
from .common_message import CommonMessage
from .custom_tree import ConversationTree, MyDirectoryTree
from .fun_zone import FunZone, JustBeing, BombBoom, RotatingCube
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
from .theme import ThemeColor
from .theme import theme_color as tc
from .voice import Voice
from .wink_wink import Horse
from ..controllers.assistant_tube_control import AssistantTube
from ..controllers.chat_context_control import ChatContextControl
from ..controllers.chat_response_control import ChatResponse
from ..controllers.dash_board_control import DashBoard
from ..controllers.decorate_display_control import DecorateDisplay
from ..controllers.group_talk_control import GroupTalkControl
from ..controllers.notification_control import Notification
from ..controllers.openai_chat_manage import OpenaiChatManage
from ..controllers.tube_files_control import TubeFiles
from ..controllers.voice_control import VoiceService
from ..data.vector_memory.qdrant_memory import QdrantVector
from ..drivers.driver_manager import DriverManager
from ..models.context import OpenaiContext
from ..models.doc import Doc, document_loader
from ..models.gptui_basic_services.plugins.conversation_service import ConversationService
from ..models.jobs import GroupTalkManager
from ..models.openai_chat import OpenaiChat
from ..models.utils.openai_api import openai_api
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


class MainScreen(Screen):
    def __init__(self, main_app: MainApp, *args, **kwargs) -> None:
        self.main_app = main_app
        super().__init__(*args, **kwargs)

    def compose(self) -> ComposeResult:
        yield AppStart(self.main_app, classes="top_layer")
        with Horizontal():
            with Vertical(id = "text_region"):
                with Horizontal(id = "tabs_region"):
                    with Vertical(classes="dot_display"):
                        yield NoPaddingButton("\ueab5", classes="tab_arrow", id="tab_left")
                        yield Label(Text("1", tc("yellow") or "yellow"), id="tabs_num_display")
                    yield Tabs(id="chat_tabs")
                    with Vertical(classes="dot_display"):
                        yield NoPaddingButton("\ueab6", classes="tab_arrow", id="tab_right")
                        yield Label(Text(u'\u260a', 'cyan'), id="commander_status_display")
                
                with Horizontal(id="chat_window"):
                    yield MyChatWindow(id="chat_region")
                    yield Static(id="chat_region_scroll_bar")
                
                yield MyFillIn(char=chr(0x2500), id="line_between_chat_status")
                
                yield Static(self.main_app.status_region_default, id="status_region")
                
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
                    yield ConversationTree(self.main_app.config["conversation_path"], "Conversations:", id="conversation_tree")
                    yield MyDirectoryTree(self.main_app.config["directory_tree_path"], self.main_app.config["directory_tree_path"], id="directory_tree")
                    yield MyChatWindow(id="assistant_tube")
                    yield Tube(app=self.main_app, id="file_tube")
                    with Vertical(id="plugins_region"):
                        with Horizontal():
                            yield Label("Plugins: ", id="plugin_label")
                            yield NoPaddingButton("|Refresh|", id="plugin_refresh")
                        user_plugins_up = GridContent(classes="user_plugins", id="user_plugins_up") 
                        user_plugins_down = GridContent(classes="user_plugins", id="user_plugins_down")
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
                        yield Static(" R", classes="switch_label")
                        tui_config = self.main_app.config["tui_config"]
                        assert isinstance(tui_config, dict)
                        yield Switch(value=tui_config["conversations_recover"], id="conversations_recover", classes="min_switch")
                        yield Static(" V", classes="switch_label")
                        yield Switch(value=tui_config["voice_switch"], id="voice_switch", classes="min_switch")
                        yield Static(" S", classes="switch_label")
                        yield Switch(value=tui_config["speak_switch"], id="speak_switch", classes="min_switch")
                        yield Static(" C", classes="switch_label")
                        yield Switch(value=tui_config["ai_care_switch"], id="ai_care_switch", classes="min_switch")
                        yield Static(" F", classes="switch_label")
                        yield Switch(value=tui_config["file_wrap_display"], id="file_wrap_display", classes="min_switch")
                    yield NoPaddingButton("|Exit|", id="exit")


class MainApp(App[str]):

    CSS_PATH = "layout.tcss"

    BINDINGS = [
        Binding("escape,ctrl+underscore", "hot_key", "active hot key"),
        Binding("ctrl+q", "exit_main_app", "exit the app"),
        Binding("ctrl+n", "add_conversation", "add a conversation"),
        Binding("ctrl+s", "save_conversation", "save a conversation"),
        Binding("ctrl+r", "delete_conversation", "delete a conversation"),
        Binding("ctrl+t", "change_to_assistant_tube", "change_to_assistant_tube"),
        Binding("ctrl+g", "change_to_file_tube", "change_to_file_tube"),
        Binding("ctrl+p", "change_to_plugins_region", "change_to_plugins_region"),
        Binding("ctrl+o", "toggle_monochrome", "toggle_monochrome"),
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
        self.color_theme: str = "default"
        self.main_screen = MainScreen(self)
    
    async def on_mount(self):
        await self.push_screen(self.main_screen)
        self.main_screen.query_one("#no_text_region_content_switcher").current = "conversation_tree"
        self.main_screen.query_one("#control_panel").current = "info_display"
        self.main_screen.query_one("#input_switcher").current = "message_region"
        self.main_screen.query_one("#message_region").focus()

    async def on_ready(self):
        status = await self.app_init()
        if status is False:
            return
        message_region = self.main_screen.query_one("#message_region")
        message_region.border_title = u'\u2500' * self.main_screen.query_one("#message_region").content_size.width
        message_region.border_subtitle = u'\u2500' * self.main_screen.query_one("#message_region").content_size.width
        self.main_screen.query_one("#control_panel").border_subtitle = "Control Panel"
        assistant_tube = self.main_screen.query_one("#assistant_tube")
        assistant_tube.border_title = "Assistant Tube"
        assistant_tube.border_subtitle = "[@click=app.assistant_tube_clear]Clear Tube[/]"
        self.no_context_manager = NoContextChat(self)
        # rebuild conversations in last running.
        self.run_worker(self.conversations_display_init(conversation_active=self.openai.conversation_active))
        self.service_init()
        self.main_screen.query_one("#conversation_tree").conversation_refresh()
    
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
            self.main_screen.query_one("#chat_tabs").action_previous_tab()
        
        elif event.button.id == "tab_right":
            self.main_screen.query_one("#chat_tabs").action_next_tab()

        elif event.button.id == "fold_no_text_region":
            button = self.main_screen.query_one("#fold_no_text_region")
            no_text_region = self.main_screen.query_one("#no_text_region")
            if str(button.label) == "\u21a3":
                no_text_region.add_class("folded")
                button.label = "\u21a2"
            else:
                no_text_region.remove_class("folded")
                button.label = "\u21a3"

        elif event.button.id == "exit":
            await self.action_exit_main_app()
        
        elif event.button.id == "import_file_to_tube":
            file_path = self.main_screen.query_one("#directory_tree").file_path_now
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
                        others=Text("Selected file type is not suppported.", tc("yellow") or "yellow"),
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
            file_tube = self.main_screen.query_one("#file_tube")
            file_tube.add_document_to_up_tube(document=doc)
            self.main_screen.query_one("#middle_switch").change_to_pointer("file_tube")
        
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
            
            # If there is no chat window, then send the input to 'horse'.
            if self.main_screen.query_one("#chat_tabs").tab_count == 0:
                self.horse.refresh_input(input)
                return
            
            upload_file_switch = self.main_screen.query_one("#file_tube #send_switch")
            tab = self.main_screen.query_one("#chat_tabs").active_tab

            if not tab:
                Thread(target = self.no_context_manager.chat, args = (input,)).start()
                return
            
            tab_mode = tab.id[:3]
            
            if tab_mode == "ncc":
                Thread(target = self.no_context_manager.chat, args = (input,)).start()
                return
            elif tab_mode == "lxt":
                group_talk_manager = self.openai.group_talk_conversation_dict[self.openai.group_talk_conversation_active]["group_talk_manager"]
                self.group_talk_chat(input_text=input, group_talk_manager=group_talk_manager)
                return
            
            context = self.openai.conversation_dict[self.openai.conversation_active]["openai_context"]
            stream = context.parameters.get("stream", True)

            # If the upload_file_switch is on, append the content of the file to the prompt.
            if upload_file_switch.value:
                displayer = self.main_screen.query_one("#status_region")
                tf = TubeFiles(displayer=displayer)
                tube = self.main_screen.query_one("#file_tube")
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
                        others=Text(f"Unable to parse the command: {message.value}", tc("yellow") or "yellow"),
                    )
                )

    async def on_voice_submitted(self, message) -> None:
        tab = self.main_screen.query_one("#chat_tabs").active_tab
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
            height = self.main_screen.query_one("#chat_region_scroll_bar").content_size.height
            content = self.scroll_bar_content(message.my_scroll, height)
            self.main_screen.query_one("#chat_region_scroll_bar").update(content)

    async def on_slider_slider_changed(self, event) -> None:
        if event.slide_switch.id == "control_switch":
            self.main_screen.query_one("#control_panel").current = event.slider.pointer
            if event.slider.pointer == "info_display":
                self.chat_parameters_display()
        elif event.slide_switch.id == "middle_switch":
            self.main_screen.query_one("#no_text_region_content_switcher").current = event.slider.pointer
            # scroll the assistant tube to end
            await asyncio.sleep(0.2) # wait the assistant tube to mount to get the correct width
            if event.slider.pointer == "assistant_tube":
                assistant_tube = self.main_screen.query_one("#assistant_tube")
                assistant_tube.refresh_content_wrap_request_execute()
                assistant_tube.scroll_to_end(refresh=True)
            elif event.slider.pointer == "plugins_region":
                if self.openai.conversation_active > 0:
                    self.plugin_refresh()
            elif event.slider.pointer == "directory_tree":
                self.main_screen.query_one("#directory_tree").reload()
            elif event.slider.pointer == "conversation_tree":
                self.main_screen.query_one("#conversation_tree").conversation_refresh()
    
    async def on_switch_changed(self, event) -> None:
        if event.switch.id == "voice_switch":
            if event.value:
                voice = Voice(self, dot_env_path=self.config["dot_env_path"], max_record_time=60)
                self.main_screen.query_one("#voice_input").mount(voice)
                self.main_screen.query_one("#input_switcher").current = "voice_input"
                self.main_screen.query_one("#speak_switch").value = True
                await asyncio.sleep(0.5)
                self.main_screen.query_one("Voice").focus()
            else:
                self.main_screen.query_one("#input_switcher").current = "message_region"
                voice = self.main_screen.query_one("Voice")
                if voice:
                    voice.remove()
                self.main_screen.query_one("#speak_switch").value = False
                self.main_screen.query_one("#message_region").focus()
        elif event.switch.id == "speak_switch":
            if event.value is True:
                self.voice_service.connect()
            else:
                self.voice_service.cancel_speak()
        elif event.switch.id == "file_wrap_display":
            tab_id = self.main_screen.query_one("#chat_tabs").active
            if not tab_id:
                return
            id = int(tab_id[3:])
            if id > 0:
                self.openai.conversation_active = id
                conversation_chat_context = self.openai.conversation_dict[id]["openai_context"].chat_context
                self.context_to_chat_window(conversation_chat_context)
            else:
                self.no_context_manager.no_context_chat_active = id
                self.context_to_chat_window(self.no_context_manager.no_context_chat_dict[self.no_context_manager.no_context_chat_active])

    def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
        tab_id = event.tab.id
        assert tab_id is not None
        id = int(tab_id[3:])
        tab_mode = tab_id[:3]
        if tab_mode != "ncc":
            self.openai.ai_care.reset()
        if tab_mode == "lxt":
            # lxt: Group talk.
            # Update commander_status_display
            commander_status_display = self.main_screen.query_one("#commander_status_display")
            if self.notification.commander_status.get(id, False):
                commander_status_display.update(Text('\u2725', tc("green") or "green"))
            else:
                commander_status_display.update(Text('\u2668', tc("red") or "red"))
            
            self.openai.group_talk_conversation_active = id
            group_talk_manager = self.openai.group_talk_conversation_dict[id]["group_talk_manager"]
            roles_list = list(group_talk_manager.roles.values())
            if not roles_list:
                self.main_screen.query_one("#chat_region").clear()
                return
            first_role = roles_list[0]
            
            # Change role view
            first_view_context = change_role_view(
                context=first_role.context.chat_context,
                from_view=first_role.name,
                to_view=group_talk_manager.user_name,
            )

            self.chat_display.tab_not_switching.clear()
            self.context_to_chat_window(first_view_context)
            self.chat_display.tab_not_switching.set()
            tokens_window = self.get_tokens_window(first_role.context.parameters.get("model"))
            self.dash_board.group_talk_dash_board_display(tokens_window, conversation_id=id)
            self.main_screen.query_one("#status_region").update(self.status_region_default)
            self.main_screen.query_one("#message_region").focus()
            self.register_plugins_to_manager()
            self.register_default_plugins_to_manager()
            self.plugin_refresh()
            self.chat_parameters_display()
        elif tab_mode == "lqt":
            # lqt: Normal chat.
            # Update commander_status_display
            commander_status_display = self.main_screen.query_one("#commander_status_display")
            if self.notification.commander_status.get(id, False):
                commander_status_display.update(Text("\u260d", tc("red") or "red"))
            else:
                commander_status_display.update(Text("\u260c", tc("green") or "green"))
            
            self.openai.conversation_active = id
            openai_context = self.openai.conversation_dict[id]["openai_context"]
            self.chat_display.tab_not_switching.clear()
            self.context_to_chat_window(openai_context.chat_context)
            self.chat_display.tab_not_switching.set()
            tokens_window = self.get_tokens_window(openai_context.parameters.get("model"))
            self.dash_board.dash_board_display(tokens_window, conversation_id=id)
            self.main_screen.query_one("#status_region").update(self.status_region_default)
            self.main_screen.query_one("#message_region").focus()
            self.register_plugins_to_manager()
            self.register_default_plugins_to_manager()
            self.plugin_refresh()
            self.chat_parameters_display()
        elif tab_mode == "ncc":
            # ncc: No chat context
            self.no_context_manager.no_context_chat_active = id
            self.context_to_chat_window(self.no_context_manager.no_context_chat_dict[self.no_context_manager.no_context_chat_active])
            dashboard = self.main_screen.query_one("#dash_board")
            height = dashboard.content_size.height
            dashboard.update(Text(" X \n" * height, tc("red") or "red"))
            self.main_screen.query_one("#status_region").update(Text("Disposable chat now.", tc("yellow") or "yellow"))
            self.main_screen.query_one("#message_region").focus()
        # Refresh the tabs number.
        tab_num = self.main_screen.query_one("#chat_tabs").tab_count
        if tab_num > 9:
            tab_num = u'\u21DE'
        self.main_screen.query_one("#tabs_num_display").update(Text(str(tab_num), tc("yellow") or "yellow"))

    async def on_tabs_cleared(self, event: Tabs.Cleared) -> None:
        self.openai.conversation_active = 0
        chat_region = self.main_screen.query_one("#chat_region")
        chat_region_width = chat_region.content_size.width
        chat_region_height = chat_region.content_size.height
        chat_region.clear()
        fun_zone = FunZone(chat_region)
        apples = [JustBeing(), BombBoom(), RotatingCube(happy_width=chat_region_width, happy_height=chat_region_height)]
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
                        others=Text("There is no conversation currently available for plugins.", tc("yellow") or "yellow"),
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
            file_tube = self.main_screen.query_one("#file_tube")
            file_tube.add_document_to_down_tube(document=document)
            self.main_screen.query_one("#middle_switch").change_to_pointer("file_tube")
        if message.message_name == "vector_memory_write":
            message_content = message.message_content
            self.qdrant_queue.put({"action": "write_reference", "content": message_content})
        if message.message_name == "open_group_talk":
            message_content = message.message_content
            tab_id = message_content["tab_id"]
            tab_name = message_content["tab_name"]
            chat_tabs = self.main_screen.query_one("#chat_tabs")
            chat_tabs.add_tab(Tab(tab_name, id=tab_id))

    def action_set_chat_parameters(self, parameters: dict) -> None:
        # valid check
        if not isinstance(parameters, dict):
            self.main_screen.query_one("#status_region").update(Text("'parameters' have to be a dict.", tc("red") or "red"))
            return

        self.openai.conversation_dict[self.openai.conversation_active]["openai_context"].parameters.update(parameters)
        self.calibrate_chat_parameters(self.openai.conversation_active)
        self.chat_parameters_display()

    def action_set_max_sending_tokens_ratio(self, ratio: float) -> None:
        # valid check
        if not isinstance(ratio, float):
            self.main_screen.query_one("#status_region").update(Text("'max_sending_tokens_ratio' have to be a flat number."), tc("red") or "red")
            return
        if not 0.0 < ratio < 1.0:
            self.main_screen.query_one("#status_region").update(Text("'max_sending_tokens_ratio' have to be in range from 0.0 to 1.0."), tc("red") or "red")
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
        assistant_tube=self.main_screen.query_one("#assistant_tube")
        assistant_tube.clear()

    # Shortcut keys ###############################################################################################
    async def action_exit_main_app(self):
        app_state = {"conversations_recover": self.main_screen.query_one("#conversations_recover").value}
        try:
            with open(os.path.join(self.workpath, "_last_app_state.json"), "w") as write_file:
                write_file.write(json.dumps(app_state, ensure_ascii = False, sort_keys = True, indent = 4, separators = (',',':')))
        except Exception as e:
            state_write_status = False
            gptui_logger.error(f"Write app last state failed. Error: {e}")
        else:
            state_write_status = True
        switch = self.main_screen.query_one("#conversations_recover")
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
                self.main_screen.query_one("#status_region").update("Caching conversation vectors ...")
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
                self.main_screen.query_one("#status_region").update(Text("Conversation vectors cached.", tc("green") or "green"))
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
                    self.manager.gk_kernel.commander.exit()
                    self.exit("Conversation is cached successfully.")
                else:
                    self.run_worker(self.exit_check("GPTUI state is not saved successfully, do you want to exit without save?"))
        else:
            if state_write_status:
                self.qdrant_queue.put({"action": "STOP"})
                self.qdrant_thread.join()
                self.manager.gk_kernel.commander.exit()
                self.exit("GPTUI's last state was saved successfully.")
            else:
                self.run_worker(self.exit_check("GPTUI state is not saved successfully, do you want to exit without save?"))

    async def action_add_conversation(self):
        await self.horse.stop_async()
        conversation_id = self.openai.open_conversation_with_mode()
        self.openai.conversation_active = conversation_id
        tab_id = "lqt" + str(conversation_id)
        tab_name = self.openai.conversation_dict[self.openai.conversation_active]["tab_name"]
        chat_tabs = self.main_screen.query_one("#chat_tabs")
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
                    others=Text("Conversations are cleared.", tc("yellow") or "yellow"),
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
        if self.main_screen.query_one("#chat_tabs").tab_count == 0:
            return
        self.run_worker(self.delete_conversation_check())

    async def action_new_disposable_chat(self):
        no_context_chat_id = self.no_context_manager.open_no_context_chat()
        self.no_context_manager.no_context_chat_active = no_context_chat_id
        tab_id = "ncc" + str(no_context_chat_id)
        self.main_screen.query_one("#chat_tabs").add_tab(Tab("NoCo", id=tab_id))
        await asyncio.sleep(0.2)
        self.main_screen.query_one("#chat_tabs").active = tab_id
        self.context_to_chat_window([])

    async def action_read_conversation(self):
        conversation_file_now = self.main_screen.query_one("#conversation_tree").file_path_now
        if conversation_file_now:
            status, info = self.openai.read_conversation(str(conversation_file_now))
            if status is False:
                if isinstance(info, int):
                    # The conversation already exits, switch to that conversation
                    self.main_screen.query_one("#chat_tabs").active = "lqt" + str(info)
                    return
                else:
                    return
            self.context_to_chat_window(self.openai.conversation_dict[self.openai.conversation_active]["openai_context"].chat_context)
            tab_name = self.openai.conversation_dict[self.openai.conversation_active]["tab_name"]
            tab_id = str(self.openai.conversation_active)
            tab_id = "lqt" + tab_id
            self.main_screen.query_one("#chat_tabs").add_tab(Tab(tab_name, id=tab_id))
            await asyncio.sleep(0.2)
            self.main_screen.query_one("#chat_tabs").active = tab_id
        else:
            self.main_screen.query_one("#status_region").update(Text("No conversation selected.", tc("yellow") or "yellow"))

    async def action_delete_conversation_file(self):
        conversation_tree = self.main_screen.query_one("#conversation_tree")
        if self.main_screen.query_one("#middle_switch").index != 0:
            ani_id = uuid.uuid4()
            self.post_message(
                AnimationRequest(
                    ani_id=ani_id,
                    action="start",
                    ani_type="static",
                    keep_time=3,
                    ani_end_display=self.status_region_default,
                    others=Text(
                        "Only conversation files can be deleted. "
                        "Switch to the conversation list first.",
                        tc("yellow") or "yellow"
                    ),
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
                    others=Text("No conversation is selected.", tc("yellow") or "yellow"),
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
                            others=Text("The conversation selected does not exist", tc("red") or "red"),
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
                            others=Text(f"An error occurred while deleting conversation file: {e}", tc("red") or "red"),
                        )
                    )
                else:
                    conversation_tree.conversation_refresh()
            else:
                return

        self.push_screen(
            CheckDialog(
                prompt=Text(
                    "Are you sure you want to delete this conversation file?\n"
                    "Note: Once deleted, it cannot be recovered.",
                    tc("yellow") or "yellow"
                )
            ),
            check_dialog_handle,
        )

    def action_change_to_assistant_tube(self):
        self.main_screen.query_one("#middle_switch").change_to_pointer("assistant_tube")
    
    def action_change_to_file_tube(self):
        self.main_screen.query_one("#middle_switch").change_to_pointer("file_tube")

    def action_change_to_plugins_region(self):
        self.main_screen.query_one("#middle_switch").change_to_pointer("plugins_region")
    
    def action_hot_key(self):
        hot_key_display = textwrap.dedent(
            """
            | n -> new chat            w -> save chat           l -> load chat       |
            | r -> remove chat         x -> delete chat file    o -> disposable chat |
            | c -> conversation_tree   d -> directory_tree      a -> assistant_tube  |
            | t -> file_tube           p -> plugins_region      i -> info_display    |
            | s -> command_input       9 -> left chat           0 -> right chat      |
            | f -> focus conversation  h -> help                z -> file_wrap       |
            | k -> toggle speak        v -> toggle voice        q -> return          |
            | m -> focus input         b -> toggle ai_care      u -> fold right      |
            """
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
            self.main_screen.query_one("#middle_switch").change_to_pointer("conversation_tree")
        elif key == "d":
            self.main_screen.query_one("#middle_switch").change_to_pointer("directory_tree")
        elif key == "a":
            self.main_screen.query_one("#middle_switch").change_to_pointer("assistant_tube")
        elif key == "t":
            self.main_screen.query_one("#middle_switch").change_to_pointer("file_tube")
        elif key == "p":
            self.main_screen.query_one("#middle_switch").change_to_pointer("plugins_region")
        elif key == "i":
            self.main_screen.query_one("#control_switch").change_to_pointer("info_display")
        elif key == "s":
            self.main_screen.query_one("#control_switch").change_to_pointer("command_input")
            self.main_screen.query_one("#command_input").focus()
        elif key == "9":
            self.main_screen.query_one("#chat_tabs").action_previous_tab()
        elif key == "0":
            self.main_screen.query_one("#chat_tabs").action_next_tab()
        elif key == "f":
            self.main_screen.query_one("#middle_switch").change_to_pointer("conversation_tree")
            self.main_screen.query_one("#conversation_tree").focus()
        elif key == "h":
            self.main_screen.query_one("#help").press()
        elif key == "z":
            self.main_screen.query_one("#file_wrap_display").toggle()
        elif key == "k":
            self.main_screen.query_one("#speak_switch").toggle()
        elif key == "v":
            self.main_screen.query_one("#voice_switch").toggle()
        elif key == "m":
            self.main_screen.query_one("#message_region").focus()
        elif key == "b":
            self.main_screen.query_one("#ai_care_switch").toggle()
        elif key == "u":
            self.main_screen.query_one("#fold_no_text_region").press()

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
        self.main_screen.query_one("#info_display").update(display)
    
    def tab_rename(self, tab: Tab, name: Text | str) -> None:
        tab.label = Text.from_markup(name) if isinstance(name, str) else name
        tab.update(name)
        underline = self.main_screen.query_one("#chat_tabs").query_one(Underline)
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
            self.app.openai.accept_ai_care = False
            self.app.openai.reset_ai_care_depth()
            self.app.openai.openai_chat.chat(message=piece, context=self.context)
            # Since chat is a non-blocking operation now, the conversation tab rename operation here has been
            # moved into 'notification_control.py'.
            # The rename operation is executed after determining the completion of the chat job.

    def chat_thread(self, input_text: str, context: OpenaiContext):
        thread_chat = self.ChatThread(self, input_text, context)
        thread_chat.start()

    @work(exclusive=True, thread=True)
    def chat_stream(self, input_text: str, context: OpenaiContext) -> None:
        piece = {"role": "user", "content": input_text}
        self.context_piece_to_chat_window(piece, change_line=True, decorator_switch=True)
        self.openai.accept_ai_care = False
        self.openai.reset_ai_care_depth()
        self.openai.openai_chat.chat_stream(message=piece, context=context)
        # Since chat is a non-blocking operation now, the conversation tab rename operation here has been
        # moved into 'notification_control.py'.
        # The rename operation is executed after determining the completion of the chat job.

    @work(exclusive=True, thread=True)
    def group_talk_chat(self, input_text: str, group_talk_manager: GroupTalkManager) -> None:
        self.post_message(
            AnimationRequest(
                ani_id=uuid.uuid4(),
                action="start",
                ani_type="static",
                keep_time=2,
                ani_end_display=self.status_region_default,
                others=Text("The message will be sent as soon as possible.", tc("green") or "green"),
            )
        )
        self.openai.openai_group_talk.talk_stream(group_talk_manager=group_talk_manager, message_content=input_text)

    def conversation_tab_rename(self, context: OpenaiContext):
        conversation_id = context.id
        tab_id = "lqt" + str(conversation_id)
        tab = self.main_screen.query_one(f"#chat_tabs #{tab_id}")
        tokens_num = context.tokens_num
        assert tokens_num is not None
        if (tab.label_text == "None" or tab.label_text == "New") and tokens_num >= 200:
            self.main_screen.query_one("#status_region").update("Conversation renaming...")
            try:
                rename_function = self.manager.services.sk_kernel.skills.get_function("conversation_service", "conversation_title")
                conversation = context.chat_context
                conversation_str = json.dumps(conversation, ensure_ascii = False, sort_keys = True, indent = 4, separators = (',',':'))
                name = str(rename_function(conversation_str))
                name = name.replace("\n", "") # '\n' may cause tab name display error, because tab have only one line.
            except Exception as e:
                self.main_screen.query_one("#status_region").update(
                    Text(
                        "Rename error: " + type(e).__name__,
                        tc("yellow") or "yellow"
                    )
                )
                gptui_logger.info("Rename failed.")
            else:
                self.openai.conversation_dict[conversation_id]["tab_name"] = name
                self.tab_rename(tab, name)
                self.main_screen.query_one("#status_region").update(self.status_region_default)
    
    def scroll_bar_content(self, scroll, height):
        y_start = math.floor(scroll.y_start * height)
        y_end = math.ceil(scroll.y_end * height)
        if scroll.y_start == 0 and scroll.y_end == 1:
            content = Text()
        else:
            content = Text()
            content.append_text(Text(u'\u00b7\n'*y_start, tc("yellow") or "yellow"))
            content.append_text(Text('-\n'*(y_end-y_start), tc("blue") or "blue"))
            content.append_text(Text(u'\u00b7\n'*(height-y_end), tc("yellow") or "yellow"))
        return content

    # context to chat window
    ############################################################################## context to chat window
    def context_to_chat_window(self, context: list[dict], change_line: bool = True) -> None:
        self.main_screen.query_one("#chat_region").clear()
        self.decorate_display.clear_code_block() # clear code_block DecorateDisplay
        for piece in context:
            piece_content = {"role": piece["role"], "name": piece.get("name", None), "content": piece["content"]}
            self.context_piece_to_chat_window(piece=piece_content, change_line=change_line, decorator_switch=True)

    def context_piece_to_chat_window(self, piece: dict, change_line: bool = False, decorator_switch: bool = False) -> None:
        chat_region = self.main_screen.query_one("#chat_region")
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
        display = self.main_screen.query_one("#assistant_tube")
        if piece["content"].endswith('\n'):
            end = '\n'
        else:
            end = '\n\n'
        if piece["role"] == "assistant_app":
            chat_content = \
                Text.from_markup(f"[black on {tc('white') or 'white'}]Assistant:[/]\n")\
                + Text(piece["content"] + end, tc("yellow") or "yellow")
        elif piece["role"] == "gpt":
            chat_content = \
                Text.from_markup(f"[black on {tc('white') or 'white'}]GPT:[/]\n")\
                + Text(piece["content"] + end, tc("green") or "green")
        elif piece["role"] == "function":
            name = piece["name"]
            chat_content = \
                Text.from_markup(f"[black on {tc('white') or 'white'}]Function:[/]")\
                + Text.from_markup(f"[bold {tc('blue') or 'blue'}] {name}[/]\n")\
                + Text(piece["content"] + end, tc("yellow") or "yellow")
        elif piece["role"] == "other":
            chat_content = \
                Text.from_markup(f"[black on {tc('white') or 'white'}]Other from gpt:[/]\n")\
                + Text(piece["content"] + end, tc("red") or "red")
        else:
            chat_content = None
        if chat_content is not None:
            if self.main_screen.query_one("#no_text_region_content_switcher").current == "assistant_tube":
                display.write(chat_content)
            else:
                display.write_content_without_display(chat_content)

    def filter(self, piece: dict) -> dict | None:
        role = piece["role"]
        name = piece.get("name", None)
        content = piece["content"]
        if content is None:
            return
        if role == "system":
            return
        elif role == "group_talk_assistant":
            if name == "host":
                return
            if content == "Can I speak?" or content == " ":
                return
        elif role == "tool":
            return

        return piece

    def decorator(
        self,
        piece: dict,
        stream: bool = False,
        copy_code: bool = True,
        emoji: bool = True
    ) -> Lines:
        content = piece["content"]
        role = piece["role"]
        name = piece.get("name", None)

        displayer = self.main_screen.query_one("#chat_region")
        width = displayer.content_size.width
        if emoji:
            content = Emoji.replace(content)
        wrap_file = self.main_screen.query_one("#file_wrap_display").value
        out = self.decorate_display.pre_wrap_and_highlight(
            inp_string=content,
            stream=stream,
            copy_code=copy_code,
            wrap={"file_wrap":{"wrap": wrap_file, "wrap_num": 4}})
        
        # Reset the decorate_display chain
        self.decorate_display.get_and_reset_chain()
        chain = self.decorate_display.background_chain(out, width-5)
        
        def string_to_color(s) -> str:
            # Translate a string to a color
            m = hashlib.md5()
            m.update(s.encode('utf-8'))
            h = int(m.hexdigest(), 16)
            r = (h & 0xFF0000) >> 16
            g = (h & 0x00FF00) >> 8
            b = h & 0x0000FF
            return "#{:02X}{:02X}{:02X}".format(r, g, b)

        if name is None:
            if role == "user":
                color = tc("user_message") or "green"
            elif role == "assistant":
                color = tc("assistant_message") or "red"
            elif role == "system":
                color = tc("system_message") or "yellow"
            else:
                color = tc("white") or "white"
            chain.panel_chain(panel_color=color).indicator_chain(indicator_color=color)
            return chain.chain_lines
        else:
            color = string_to_color(name)
            if role in {"user", "group_talk_user"}:
                role_icon = Emoji.replace(":man:")
            elif role in {"assistant", "group_talk_assistant"}:
                role_icon = Emoji.replace(":robot:")
            else:
                role_icon = ""
            role_length = Text(role_icon + name).cell_len
            role_display = Lines(
                [
                    Text(u'\u256D' + u'\u2500' * role_length + u'\u256E'),
                    Text(u'\u2502' + role_icon + name + u'\u2502'),
                ]
            )
            chain.panel_chain(panel_color=color)
            role_display.extend(chain.chain_lines)
            chain.chain_lines = role_display
            chain.indicator_chain(indicator_color=color)
            return chain.chain_lines
    
    def get_tokens_window(self, model: str) -> int:
        """Query tokens window for openai model from config.
        Return 0 if no corresponding tokens window for model in config.
        """
        model_info = self.config["openai_model_info"].get(model)
        if model_info is None:
            return 0
        else:
            return model_info.get("tokens_window") or 0
    
    async def delete_conversation_check(self) -> None:
        tabs = self.main_screen.query_one("#chat_tabs")
        old_tab_id = tabs.active_tab.id
        if int(old_tab_id[3:]) < 0:
            tabs.remove_tab(old_tab_id)
            self.no_context_manager.no_context_chat_delete(int(old_tab_id[3:]))
            return

        def check_dialog_handle(confirm: bool) -> None:
            if confirm:
                tab_mode = old_tab_id[:3]
                tabs.remove_tab(old_tab_id)
                if tab_mode == "lqt":
                    self.openai.delete_conversation(conversation_id=int(old_tab_id[3:]))
                elif tab_mode == "lxt":
                    self.openai.delete_group_talk_conversation(group_talk_conversation_id=int(old_tab_id[3:]))
                self.chat_display.delete_buffer_id(id=int(old_tab_id[3:]))
            else:
                return

        self.push_screen(CheckDialog(prompt="Are you sure to close this conversation?\nUnsaved conversations will not be saved."), check_dialog_handle)

    async def exit_check(self, prompt: Text|str) -> None:
        def check_dialog_handle(confirm: bool) -> None:
            if confirm:
                self.qdrant_queue.put({"action": "STOP"})
                self.qdrant_thread.join()
                self.manager.gk_kernel.commander.exit()
                self.exit()
            else:
                return
        self.push_screen(CheckDialog(prompt=prompt), check_dialog_handle)
    
    async def message_region_border_reset(self) -> None:
        """Refresh the border display of the message_region"""
        message_region = self.main_screen.query_one("#message_region")
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
        chat_tabs = self.main_screen.query_one("#chat_tabs")
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
        plugin_display_up = self.main_screen.query_one("#user_plugins_up")
        plugin_display_up.clear()
        plugin_display_down = self.main_screen.query_one("#user_plugins_down")
        plugin_display_down.clear()
        plugins_actived = self.openai.conversation_dict[self.openai.conversation_active]["openai_context"].plugins
        for plugin in native_plugins_list:
            if plugin.plugin_info[2] in self.config["user_plugins_up"]:
                plugin_display_up.add_children(
                    MyCheckBox(
                        status=(plugin.plugin_info in plugins_actived),
                        icon=Text("  \U000F0880 ", tc("blue") or "blue"),
                        label=Text(plugin.name),
                        pointer=plugin,
                        domain=plugin_display_up
                    )
                )
            else:
                plugin_display_down.add_children(
                    MyCheckBox(
                        status=(plugin.plugin_info in plugins_actived),
                        icon=Text("  \U000F0880 ", tc("blue") or "blue"),
                        label=Text(plugin.name),
                        pointer=plugin,
                        domain=plugin_display_down
                    )
                )
        for plugin in semantic_plugins_list:
            if plugin.plugin_info[1] in self.config["user_plugins_up"]:
                plugin_display_up.add_children(
                    MyCheckBox(
                        status=(plugin.plugin_info in plugins_actived),
                        icon=Text("  \U000F0C23 ", tc("purple") or "purple"),
                        label=Text(plugin.name),
                        pointer=plugin,
                        domain=plugin_display_up
                    )
                )
            else:
                plugin_display_down.add_children(
                    MyCheckBox(
                        status=(plugin.plugin_info in plugins_actived),
                        icon=Text("  \U000F0C23 ", tc("purple") or "purple"),
                        label=Text(plugin.name),
                        pointer=plugin,
                        domain=plugin_display_down
                    )
                )
    
    def manager_init(self, manager: Manager) -> None:
        commander_thread = threading.Thread(target=manager.gk_kernel.commander.run)
        commander_thread.start()
        manager.load_services(where=ConversationService(manager), skill_name="conversation_service")
        # The purpose of using the following manually constructed relative import is to 
        # avoid duplicate imports and errors in package identity determination caused by inconsistent package names.
        current_package = __package__
        parent_package = ".".join(current_package.split(".")[:-1])
        manager.register_jobs(module_name=f"{parent_package}.models.jobs")
        manager.register_handlers(module_name=f"{parent_package}.models.handlers")

    def service_init(self) -> None:
        self.animation_manager = AnimationManager(
            displayer={"default":self.main_screen.query_one("#status_region")},
            ani_end_display=self.status_region_default,
        )
        self.decorate_display = DecorateDisplay(self)
        self.drivers = DriverManager(self)
        self.chat_display = ChatResponse(self)
        self.voice_service = VoiceService(self, self.main_screen.query_one("#speak_switch").value)
        self.notification = Notification(self)
        self.chat_context = ChatContextControl(self)
        self.assistant_tube = AssistantTube(self)
        self.dash_board = DashBoard(self)
        self.group_talk = GroupTalkControl(self)
        self.horse = Horse()

    async def app_init(self):
        app_start = self.main_screen.query_one("AppStart")
        app_start_log = app_start.get_rich_log()
        app_start_func = self.app_init_process(app_start_log)
        app_start.set_init_func(app_start_func)
        status = await app_start.app_init()
        self.app_exited = not status
        return status
    
    async def app_init_process(self, init_log: RichLog) -> bool:
        end_status = False

        init_log.write("Preparing the Qdrant vector database ...")
        await asyncio.sleep(0.01)

        init_log.write("Import tiktoken ...")
        await asyncio.sleep(0.01)
        try:
            import tiktoken
            enc = tiktoken.get_encoding("cl100k_base")
            assert enc.decode(enc.encode("hello world")) == "hello world"
        except AssertionError:
            await self.start_failed_exit(
                init_log,
                f"An error occurred while downloading resources for tiktoken."
                "Please ensure that the network connection to OpenAI is stable."
                "If this problem persists, please reinstall tiktoken."
            )
        except Exception as e:
            init_log.write(Text(f"An error occurred during the import of tiktoken. Error: {e}", tc("red") or "red"))
            gptui_logger.error(f"An error occurred during the import of tiktoken. Error: {e}")
            await asyncio.sleep(0.1)
            await self.start_failed_exit(init_log, f"An error occurred during the import of tiktoken. Error: {e}")
            end_status = True
        else:
            init_log.write(Text("Import tiktoken done.", tc("green") or "green"))
            await asyncio.sleep(0.01)
        
        if end_status is True:
            # The 'return' is to prevent the statements below from being executed, because App.exit() does not exit immediately.
            return False

        init_log.write("Waiting for the Qdrant service to be ready ...")
        await asyncio.sleep(0.01)

        self.qdrant_ready.wait()
        init_log.write(Text("Qdrant service is ready.", tc("green") or "green"))
        await asyncio.sleep(0.01)

        init_log.write("Setting up the OpenAI service ...")
        await asyncio.sleep(0.01)
        try:
            self.openai = OpenaiChatManage(
                app=self,
                manager=self.manager,
                openai_chat=OpenaiChat(self.manager),
                workpath=self.config["conversation_path"],
                conversations_recover=self.main_screen.query_one("#conversations_recover").value,
            )
        except Exception as e:
            init_log.write(Text(f"An error occurred during setting up the OpenAI service. Error: {e}", tc("red") or "red"))
            gptui_logger.error(f"An error occurred during setting up the OpenAI service. Error: {e}")
            await asyncio.sleep(0.1)
            await self.start_failed_exit(init_log, f"An error occurred during setting up the OpenAI service. Error: {e}")
            end_status = True
        else:
            init_log.write(Text("The OpenAI service is ready.", tc("green") or "green"))
            await asyncio.sleep(0.01)
        
        if end_status is True:
            # The 'return' is to prevent the statements below from being executed, because App.exit() does not exit immediately.
            return False
        
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
            init_log.write(Text(f"An error occurred during cleaning collections. Error: {e}", tc("red") or "red"))
            gptui_logger.error(f"An error occurred during cleaning collections. Error: {e}")
            await asyncio.sleep(1)
        else:
            init_log.write(Text("Qdrant vector is clean.", tc("green") or "green"))
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
            init_log.write(Text(f"An error occurred during cleaning conversations. Error: {e}", tc("red") or "red"))
            gptui_logger.error(f"An error occurred during cleaning conversations. Error: {e}")
            await asyncio.sleep(1)
        else:
            init_log.write(Text("Qdrant is ready.", tc("green") or "green"))
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
                                text = str(message["content"]),
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
                        self.main_screen.query_one("#status_region").update(
                            Text(
                                f"Have no collection named {collection_name}. Error: {e}",
                                tc("yellow") or "yellow"
                            )
                        )
                    else:
                        self.main_screen.query_one("#status_region").update(
                            Text(
                                "Conversation vectors cached successfully.",
                                tc("green") or "green"
                            )
                        )
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
                        self.main_screen.query_one("#status_region").update(
                            Text(
                                f"Have no collection named {collection_name}. Error: {e}",
                                tc("yellow") or "yellow"
                            )
                        )
                    else:
                        self.main_screen.query_one("#status_region").update(
                            Text(
                                "Conversation vectors saved successfully.",
                                tc("green") or "green"
                            )
                        )
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
        init_log.write(
            Text(
                "Please check the log and try restarting later. "
                "The system will automatically shut down in three seconds",
                tc("red") or "red",
            )
        )
        await asyncio.sleep(1)
        init_log.write(Text("3", tc("red") or "red"))
        await asyncio.sleep(1)
        init_log.write(Text("2", tc("red") or "red"))
        await asyncio.sleep(1)
        init_log.write(Text("1", tc("red") or "red"))
        self.qdrant_thread.join()
        self.manager.gk_kernel.commander.exit()
        self.exit(exit_log)

    async def open_group_talk(self) -> int:
        await self.horse.stop_async()
        group_talk_conversation_id = self.openai.open_group_talk_conversation()
        tab_name = self.openai.group_talk_conversation_dict[group_talk_conversation_id]["tab_name"]
        tab_id = "lxt" + str(group_talk_conversation_id)
        # Only main thread can handle UI event correctly.
        self.post_message(CommonMessage(message_name="open_group_talk", message_content={"tab_id": tab_id, "tab_name": tab_name}))
        return group_talk_conversation_id

    def action_test(self):
        # For test
        pass

    def action_toggle_monochrome(self):
        self.toggle_class("monochrome")
        if ThemeColor._theme == "monochrome":
            ThemeColor.set_theme(self.color_theme)
            try:
                stop_button = self.main_screen.query_one("Voice #stop")
            except:
                pass
            else:
                stop_button.variant = "error"
        else:
            self.color_theme = ThemeColor._theme
            ThemeColor.set_theme("monochrome")
            try:
                stop_button = self.main_screen.query_one("Voice #stop")
            except:
                pass
            else:
                stop_button.variant = "success"
        chat_tabs = self.main_screen.query_one("#chat_tabs")
        active_tab = chat_tabs.active_tab
        if active_tab is not None:
            self.on_tabs_tab_activated(Tabs.TabActivated(chat_tabs, active_tab))
        for slider_switch in self.main_screen.query("SlideSwitch"):
            slider_switch.set_sliders(slider_switch.index)
        self.main_screen.query_one("#file_tube").refresh_display()


def change_role_view(context: list[dict], from_view: str, to_view: str = "admin") -> list[dict]:
    changed_context = []
    for one_message in context:
        role = one_message.get("role")
        name = one_message.get("name")
        content = one_message.get("content")
        changed_message = {}
        if role == "assistant":
            changed_message["role"] = "group_talk_assistant"
            changed_message["name"] = from_view
            changed_message["content"] = content
        elif role == "user" and name == to_view:
            changed_message["role"] = "group_talk_user"
            changed_message["name"] = name
            changed_message["content"] = content
        elif role == "user" and name != to_view:
            changed_message["role"] = "group_talk_assistant"
            changed_message["name"] = name
            changed_message["content"] = content
        else:
            continue
        changed_context.append(changed_message)
    return changed_context


class NoContextChat:
    """
    no context chat manager
    {no_context_chat_id:[{"role":role,"content":content}]}
    """
    def __init__(self, app: MainApp) -> None:
        self.app = app
        self.openai_api = openai_api(app.config["dot_env_path"])
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
            response = self.openai_api.ChatCompletion.create(
                model = app.config["default_openai_parameters"]["model"] or "gpt-4",
                messages = [message],
                stream = app.config["default_openai_parameters"]["stream"],
                )
        except Exception as e:
            app.post_message(AnimationRequest(ani_id=ani_id, action="end"))
            self.app.main_screen.query_one("#status_region").update(Text(f"An error occurred during communication with OpenAI. Error: {e}"))
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
                    app.main_screen.query_one("#status_region").update(Text("Response exceeds tokens limit", tc("red") or "red"))
                    break
                elif chunk.choices[0].finish_reason == "content_filter":
                    app.main_screen.query_one("#status_region").update(Text("Omitted content due to a flag from our content filters", tc("red") or "red"))
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
        chat_region = self.app.main_screen.query_one("#chat_region")
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
        if self.app.main_screen.query_one("#speak_switch").value:
            subprocess.Popen(['termux-tts-speak', speak_text])
