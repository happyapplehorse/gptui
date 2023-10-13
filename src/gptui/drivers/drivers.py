from __future__ import annotations
import logging
import os
import pyperclip
import subprocess
import threading
import time

from .driver_interface import DriverInterface


gptui_logger = logging.getLogger("gptui_logger")


class CopyCode(DriverInterface):
    
    def termux(self, content: str) -> None:
        subprocess.call(["termux-clipboard-set", content])

    def linux(self, content: str) -> None:
        pyperclip.copy(content)
    
    def macos(self, content: str) -> None:
        pyperclip.copy(content)


class TextToSpeak(DriverInterface):
    
    def termux(self, content: str):
        subp = subprocess.Popen(['termux-tts-speak', content])
        return subp

    def linux(self, content: str):
        try:
            subp = subprocess.Popen(['espeak', content])
        except FileNotFoundError:
            gptui_logger.error("The 'espeak' command is not found on this system")
        else:
            return subp
    
    def macos(self, content: str):
        try:
            subp = subprocess.Popen(['espeak', content])
        except FileNotFoundError:
            gptui_logger.error("The 'espeak' command is not found on this system")
        else:
            return subp


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
