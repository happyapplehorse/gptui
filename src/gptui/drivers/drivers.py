from __future__ import annotations
import itertools
import logging
import os
import pyperclip
import subprocess
import threading
import time
from threading import Thread
from typing import Self

from .driver_interface import DriverInterface
from ..models.utils.openai_api import openai_api_client


gptui_logger = logging.getLogger("gptui_logger")


class CopyCode(DriverInterface):
    
    def termux(self, content: str) -> None:
        subprocess.call(["termux-clipboard-set", content])

    def linux(self, content: str) -> None:
        pyperclip.copy(content)
    
    def macos(self, content: str) -> None:
        pyperclip.copy(content)


class TextToSpeak(DriverInterface):

    def __init__(self, dot_env_path: str, temp_dir: str, *args, **kwargs):
        self.openai_api_client = openai_api_client(dot_env_path=dot_env_path)
        self.temp_dir = temp_dir
        self._unique_id = itertools.count(1)
        self._audio_dict = {}
        self._now_audio_index = 1
        self._voice_service = None
        self.cond = threading.Condition()
        self.running_status = True
        super().__init__(*args, **kwargs)

    def get_audio(self, text_content: str) -> str | None:
        now_id = next(self._unique_id)
        audio_file_name = f"speech_{now_id}.mp3"
        speech_file_path = os.path.join(self.temp_dir, audio_file_name)
        try:
            response = self.openai_api_client.audio.speech.create(
                model="tts-1",
                voice="alloy",
                input=text_content,
            )
            response.stream_to_file(speech_file_path)
        except Exception as e:
            gptui_logger.error(e)
            with self.cond:
                self._now_audio_index += 1 # The current reading position scrolls forward by 1.
            return
        else:
            with self.cond:
                if self.running_status is False:
                    self._now_audio_index += 1 # The current reading position scrolls forward by 1.
                    return
                self._audio_dict[now_id] = speech_file_path
                if not self._voice_service:
                    voice_service = Thread(target=self.voice_speak)
                    voice_service.start()
                    self._voice_service = voice_service
                self.cond.notify_all()
        return speech_file_path
    
    def voice_speak(self) -> None:
        while True:
            with self.cond:
                gptui_logger.debug(f"----audio_dict_leght: {len(self._audio_dict)}")
                gptui_logger.debug(f"----audio dict: {self._audio_dict}")
                gptui_logger.debug(f"----now index: {self._now_audio_index}")
                if self._now_audio_index in self._audio_dict:
                    audio_path = self._audio_dict.pop(self._now_audio_index)
                    self._now_audio_index += 1
                    speak = True
                else:
                    speak = False
                    status = self.cond.wait(timeout=5)
                    if not status:
                        self._voice_service = None
                        break
            if speak is True:
                self.play_audio(audio_path)
                os.remove(audio_path)
    
    def play_audio(self, audio_path: str) -> None:
        subprocess.run(
            ['termux-media-player', 'play', audio_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        while True:
            result = subprocess.run(['termux-media-player', 'info'], stdout=subprocess.PIPE, text=True)
            if "Playing" not in result.stdout:
                break
            time.sleep(0.1)

    def stop(self) -> None:
        gptui_logger.debug(f"----before stop-----------index: {self._now_audio_index}")
        with self.cond:
            self.running_status = False
            if self._voice_service is None:
                return
            else:
                for value in self._audio_dict.values():
                    self._now_audio_index += 1
                    os.remove(value)
                self._audio_dict = {}
                gptui_logger.debug("------clear-----")
                gptui_logger.debug(f"----after clear: {self._audio_dict}")
        gptui_logger.debug(f"----after stop-----------index: {self._now_audio_index}")

    def termux(self, content: str) -> Self:
        with self.cond:
            self.running_status = True
        Thread(target=self.get_audio, args=(content,)).start()
        return self

    def linux(self, content: str) -> Self | None:
        try:
            subp = subprocess.Popen(['espeak', content])
        except FileNotFoundError:
            gptui_logger.error("The 'espeak' command is not found on this system")
        else:
            return self
    
    def macos(self, content: str) -> Self | None:
        try:
            subp = subprocess.Popen(['espeak', content])
        except FileNotFoundError:
            gptui_logger.error("The 'espeak' command is not found on this system")
        else:
            return self


class VoiceRecordStart(DriverInterface):
    """Only supports recording in .wav format now."""

    def __init__(self, *args, **kwargs):
        self.record_flag = True
        super().__init__(*args, **kwargs)

    def termux(self, file_path: str, max_time: int) -> tuple[int, VoiceRecordStart]:
        if os.path.isfile(file_path):
            os.remove(file_path)

        _, file_extension = os.path.splitext(file_path)
        assert file_extension == ".wav", "Only supports recording in .wav format now."
        
        exit_code = subprocess.call(['termux-microphone-record', '-l', f'{max_time}', '-f', f'{file_path}', '-e', f'{file_extension[1:]}'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return exit_code, self

    def linux(self, file_path: str, max_time: int) -> tuple[int, VoiceRecordStart]:
        
        self.record_flag = True

        if os.path.isfile(file_path):
            os.remove(file_path)

        try:
            import pyaudio
            import wave
        except ImportError as e:
            gptui_logger.error(f"Import error: {e}")
            return 1, self

        CHUNK = 1024
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 44100
        
        p = pyaudio.PyAudio()
        frames = []
        
        def record_audio():
            start_time = time.time()

            stream = p.open(format=FORMAT,
                            channels=CHANNELS,
                            rate=RATE,
                            input=True,
                            frames_per_buffer=CHUNK)

            while self.record_flag:
                elapsed_time = time.time() - start_time
                if elapsed_time > max_time:
                    break
                
                data = stream.read(CHUNK)
                frames.append(data)

            stream.stop_stream()
            stream.close()

            with wave.open(file_path, 'wb') as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(p.get_sample_size(FORMAT))
                wf.setframerate(RATE)
                wf.writeframes(b''.join(frames))

            p.terminate()
        
        record_thread = threading.Thread(target=record_audio)
        record_thread.start()

        return 0, self

    def macos(self, file_path:str, max_time: int):
        return self.linux(file_path, max_time)


class VoiceRecordQuit(DriverInterface):

    def termux(self, _):
        exit_code = subprocess.call(['termux-microphone-record','-q'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return exit_code

    def linux(self, voice_record_start_handle: VoiceRecordStart):
        voice_record_start_handle.record_flag = False
        return 0
    
    def macos(self, voice_record_start_handle: VoiceRecordStart):
        voice_record_start_handle.record_flag = False
        return 0
