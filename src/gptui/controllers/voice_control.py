import asyncio
import logging
import subprocess
from typing import Coroutine
from threading import Thread

from ..models.signals import response_to_user_message_sentence_stream_signal


gptui_logger = logging.getLogger("gptui_logger")


class VoiceService:
    def __init__(self, myapp, switch: bool = True):
        self.myapp = myapp
        self.voice_speak_queue = asyncio.Queue()
        self.speak_status = False
        self.voice_service = None
        if switch is True:
            self.connect()

    async def accept_voice_message(self, sender, **kwargs):
        voice_message = kwargs["message"]
        message_content = voice_message["content"]
        flag = voice_message["flag"]
        if self.voice_service is None:
            service_thread = self.VoiceServiceThread(self.main())
            service_thread.start()
        elif self.voice_service.done():
            service_thread = self.VoiceServiceThread(self.main())
            service_thread.start()
        if flag == "content":
            await self.voice_speak_queue.put(message_content)

    async def voice_speak(self) -> None:
        while True:
            if self.voice_speak_queue.empty():
                break
            speak_text = await self.voice_speak_queue.get()
            Thread(target=self.noblock_speak, args=(speak_text,)).start()
            self.speak_status = True
            while True:
                await asyncio.sleep(0.2)
                if not self.speak_status:
                    break

    def noblock_speak(self, speak_text: str):
        out = self.myapp.drivers.tts(speak_text)
        if isinstance(out, subprocess.Popen):
            out.wait()
        self.speak_status = False

    class VoiceServiceThread(Thread):
        def __init__(self, voice_service: Coroutine) -> None:
            super().__init__()
            self.voice_service = voice_service

        def run(self) -> None:
            asyncio.run(self.voice_service)
    
    async def main(self):
        task = asyncio.create_task(self.voice_speak())
        self.voice_service = task
        await task

    def connect(self):
        response_to_user_message_sentence_stream_signal.connect(self.accept_voice_message)

    def disconnect(self):
        response_to_user_message_sentence_stream_signal.disconnect(self.accept_voice_message)

    def cancel_speak(self) -> None:
        self.disconnect()
        if self.voice_service is None:
            return
        if self.voice_service.done():
            self.voice_service = None
            return
        
        def close_loop(loop):
            tasks = asyncio.all_tasks(loop)
            for task in tasks:
                task.cancel()
            loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
            loop.close()
        
        task = self.voice_service
        loop = task.get_loop()
        loop.call_soon_threadsafe(close_loop, loop)
        
        # clear the speak queue
        queue = self.voice_speak_queue
        while not queue.empty():
            queue.get_nowait()
