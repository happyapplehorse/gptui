import logging
import os

from .drivers import CopyCode, TextToSpeak, VoiceRecordStart, VoiceRecordQuit
from .driver_interface import DriverInterface


gptui_logger = logging.getLogger("gptui_logger")


class DriverManager:
    def __init__(self, app):
        self.app = app
        self.terminal = app.config.get("terminal")
        self.os = app.config.get("os")
        self._register_driver_method()

    def register_driver(self, driver_method_name: str, driver: DriverInterface) -> None:
        if hasattr(self, driver_method_name):
            gptui_logger.warning("A driver method with the same name already exists; it will be overwritten.")
        setattr(self, driver_method_name, driver)
    
    def _register_driver_method(self):
        self.copy_code = CopyCode(self.os)
        self.tts = TextToSpeak(
            platform=self.os,
            dot_env_path=self.app.config["dot_env_path"],
            temp_dir=os.path.join(self.app.config["workpath"], "temp"),
        )
        self.voice_record_start = VoiceRecordStart(self.os)
        self.voice_record_quit = VoiceRecordQuit(self.os)
