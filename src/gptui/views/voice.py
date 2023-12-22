import asyncio
import logging
import time
import os
from collections import deque
from time import monotonic
from typing import cast

import openai
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Button, ProgressBar, Static

from .theme import ThemeColor
from .theme import theme_color as tc
from ..models.utils.openai_api import openai_api
from ..utils.my_text import MyText as Text


gptui_logger = logging.getLogger("gptui_logger")


class TimeDisplay(Static):
    """A widget to display elapsed time."""

    start_time = reactive(monotonic)
    time = reactive(0.0)
    total = reactive(0.0)

    def on_mount(self) -> None:
        self.update_timer = self.set_interval(1 / 9, self.update_time, pause=True)

    def update_time(self) -> None:
        """Method to update time to current."""
        self.time = self.total + (monotonic() - self.start_time)

    def watch_time(self, time: float) -> None:
        """Called when the time attribute changes."""
        minutes, seconds = divmod(time, 60)
        hours, minutes = divmod(minutes, 60)
        self.update(f"{hours:02,.0f}:{minutes:02.0f}:{seconds:05.2f}")

    def start(self) -> None:
        """Method to start (or resume) time updating."""
        self.start_time = monotonic()
        self.update_timer.resume()

    def stop(self):
        """Method to stop the time display updating."""
        self.update_timer.pause()
        self.total += monotonic() - self.start_time
        self.time = self.total

    def reset(self):
        """Method to reset the time display to zero."""
        self.total = 0
        self.time = 0


class Voice(Static, can_focus=True):
    """A stopwatch widget."""

    def __init__(self, app, dot_env_path: str, max_record_time: int = 60):
        super().__init__()
        self.myapp = app
        self.max_record_time = max_record_time
        self.timer = None
        os.makedirs(os.path.join(app.config["workpath"], "temp"), exist_ok=True)
        self.progress_timer = self.set_interval(1, self.progress_drive, pause=True)
        self.key_time_deque = deque(maxlen=2)
        self.voice_record_start_handle = None
        self.openai_api = openai_api(dot_env_path)

    BINDINGS = [
        ("space", "record", "start or end record"),
    ]
    
    DEFAULT_CSS = """
    Voice {
        border: round white;
        layout: horizontal;
        background: $boost;
        height: 1fr;
        padding: 1;
    }
    TimeDisplay {
        content-align: center middle;
        text-opacity: 60%;
        height: 1;
        width: 1fr;
    }
    Button {
        width: 15;
        height: 3;
    }
    #progress_bar {
        width: 100%;
    }
    #stop {
        display: none;
    }
    #voice_status_region{
        width: 100%;
        text-align: center;
    }
    .started {
        text-style: bold;
        background: $success 30%;
        color: $text;
    }
    .started TimeDisplay {
        text-opacity: 100%;
    }
    .started #start {
        display: none
    }
    .started #stop {
        display: block
    }
    .started #send {
        visibility: hidden
    }
    .started #clear {
        visibility: hidden
    }
    """
    
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Event handler called when a button is pressed."""
        button_id = event.button.id
        time_display = self.query_one(TimeDisplay)
        
        if button_id == "start":
            self.voice_record_start(self.max_record_time)
            time_display.start()
            self.progress_timer.resume()
            self.query_one("#control_region").add_class("started")
        
        elif button_id == "stop":
            self.voice_record_quit()
            time_display.stop()
            self.progress_timer.pause()
            self.query_one("#control_region").remove_class("started")
            send_button = self.query_one("#send")
            clear_button = self.query_one("#clear")
            send_button.variant = "success"
            clear_button.variant = "success"
            send_button.disabled = False
            clear_button.disabled = False
        
        elif button_id == "send":
            self.progress_timer.pause()
            self.query_one("#voice_status_region").update(Text("Transcribing ...", tc("green") or "green"))
            def blocking_transcribe():
                try:
                    with open(os.path.join(self.myapp.config["workpath"], "temp/voice_temp.wav"), "rb") as audio_file:
                        transcript = self.openai_api.audio.transcriptions.create(
                            model="whisper-1",
                            file=audio_file,
                            response_format="text",
                        )
                except FileNotFoundError:
                    self.query_one("#voice_status_region").update(Text("Have no voice file", tc("red") or "red"))
                    return
                except openai.APIConnectionError as e:
                    self.query_one("#voice_status_region").update(Text(f"APIConnectionError: {e}", tc("red") or "red"))
                    return
                except Exception as e:
                    self.query_one("#voice_status_region").update(Text(f"Unknown error: {e}", tc("red") or "red"))
                    return
                return transcript
            transcript = await asyncio.to_thread(blocking_transcribe)
            self.query_one("#voice_status_region").update(Text("Transcription Completion!", tc("green") or "green"))
            if transcript:
                transcript_text = cast(str, transcript)
                voice_text = transcript_text.strip()
                self.post_message(self.Submitted(voice_text))
                time_display.reset()
                self.query_one("#progress_bar").update(total=self.max_record_time, progress=0)
                send_button = self.query_one("#send")
                clear_button = self.query_one("#clear")
                send_button.variant = "default"
                clear_button.variant = "default"
                send_button.disabled = True
                clear_button.disabled = True
        
        elif button_id == "clear":
            self.progress_timer.pause()
            time_display.reset()
            self.query_one("#progress_bar").update(total=self.max_record_time, progress=0)
            send_button = self.query_one("#send")
            clear_button = self.query_one("#clear")
            send_button.variant = "default"
            clear_button.variant = "default"
            send_button.disabled = True
            clear_button.disabled = True
            self.query_one("#voice_status_region").update(Text("Cleared!", tc("green") or "green"))

    def compose(self) -> ComposeResult:
        """Create child widgets of a stopwatch."""
        with Horizontal(id="control_region"):
            yield Button("Start", id="start", variant="success")
            yield Button("Stop", id="stop", variant = "success" if ThemeColor._theme == "monochrome" else "error")
            with Vertical(id="display_region"):
                yield TimeDisplay()
                yield ProgressBar(total=self.max_record_time, id="progress_bar", show_eta=False)
                yield Static(id="voice_status_region")
            yield Button("Clear", id="clear", disabled=True)
            yield Button("Send", id="send", disabled=True)

    def progress_drive(self):
        self.query_one("#progress_bar").advance(1)

    def voice_record_start(self, time: int = 60) -> None:
        exit_code, self.voice_record_start_handle = self.myapp.drivers.voice_record_start(
            os.path.join(self.myapp.config["workpath"], "temp/voice_temp.wav"),
            time,
        )
        if exit_code:
            self.query_one("#voice_status_region").update(Text(f"Record failed with exit code {exit_code}.", tc("red") or "red"))
        else:
            self.query_one("#voice_status_region").update(Text(f"Recording ...", tc("green") or "green"))

    def voice_record_quit(self) -> None:
        assert self.voice_record_start_handle is not None
        exit_code = self.myapp.drivers.voice_record_quit(self.voice_record_start_handle)
        if exit_code:
            self.query_one("#voice_status_region").update(Text(f"Record quit failed with exit code {exit_code}.", tc("red") or "red"))

    def action_record(self) -> None:
        if self.timer:
            self.timer.reset()
        else:
            self.hot_key_start()
            self.timer = self.set_timer(0.8, self.hot_key_stop)
        self.key_time_deque.append(time.time())

    def hot_key_start(self):
        self.query_one("#start").press()

    async def hot_key_stop(self):
        self.query_one("#stop").press()
        self.timer = None
        await asyncio.sleep(0.6)
        if len(self.key_time_deque) < 2:
            return
        time_interval = self.key_time_deque[1] - self.key_time_deque[0]
        if time_interval > 0.2:
            self.query_one("#clear").press()
        else:
            self.query_one("#send").press()
        self.key_time_deque.clear()

    def on_click(self):
        self.focus()

    class Submitted(Message):
        def __init__(self, content: str) -> None:
            self.content = content
            super().__init__()
