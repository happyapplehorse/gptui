from __future__ import annotations
import itertools
import logging
import os
import pyperclip
import subprocess
import threading
import time
from playsound import playsound
from threading import Thread
from typing import Callable, Self

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
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
        self.temp_dir = temp_dir
        self._unique_id = itertools.count(1)
        self._audio_dict = {}
        self._now_audio_index = 1
        self._voice_service = None
        self._start_time = 0
        self._stop_time = 0
        self._play_audio_method: Callable = self._play_audio_termux
        self.cond = threading.Condition()
        super().__init__(*args, **kwargs)

    def _get_audio(self, text_content: str) -> str | None:
        send_time = time.time()
        now_id = next(self._unique_id)
        audio_file_name = f"speech_{now_id}.mp3"
        speech_file_path = os.path.join(self.temp_dir, audio_file_name)
        try:
            response = self.openai_api_client.audio.speech.create(
                model="tts-1",
                voice="nova",
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
                if self._stop_time > self._start_time: # Stop state
                    self._now_audio_index += 1 # The current reading position scrolls forward by 1.
                    return
                if send_time < self._stop_time:
                    # Eliminate messages sent before the stop but received after the start due to delay.
                    # That is, to exclude residual messages from before the start.
                    self._now_audio_index += 1 # The current reading position scrolls forward by 1.
                    return
                self._audio_dict[now_id] = speech_file_path
                if not self._voice_service:
                    voice_service = Thread(target=self._voice_speak)
                    voice_service.start()
                    self._voice_service = voice_service
                self.cond.notify_all()
        return speech_file_path
    
    def _voice_speak(self) -> None:
        while True:
            with self.cond:
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
                self._play_audio_method(audio_path)
                os.remove(audio_path)
    
    def _play_audio_termux(self, audio_path: str) -> None:
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

    def _play_audio_linux(self, audio_path: str) -> None:
        playsound(audio_path)

    def stop(self) -> None:
        self._stop_time = time.time()
        with self.cond:
            if self._voice_service is None:
                return
            else:
                for value in self._audio_dict.values():
                    self._now_audio_index += 1
                    os.remove(value)
                self._audio_dict = {}

    def termux(self, content: str) -> Self:
        self._start_time = time.time()
        self._play_audio_method = self._play_audio_termux
        Thread(target=self._get_audio, args=(content,)).start()
        return self

    def linux(self, content: str) -> Self:
        self._start_time = time.time()
        self._play_audio_method = self._play_audio_linux
        Thread(target=self._get_audio, args=(content,)).start()
        return self
    
    def macos(self, content: str) -> Self:
        return self.linux(content)


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
