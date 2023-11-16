import logging

from ..models.signals import response_to_user_message_sentence_stream_signal


gptui_logger = logging.getLogger("gptui_logger")


class VoiceService:
    def __init__(self, myapp, switch: bool = True):
        self.myapp = myapp
        self.voice_service = None
        if switch is True:
            self.connect()

    async def accept_voice_message(self, sender, **kwargs):
        voice_message = kwargs["message"]
        message_content = voice_message["content"]
        flag = voice_message["flag"]
        if flag == "content":
            self.voice_service = self.myapp.drivers.tts(message_content)

    def connect(self):
        response_to_user_message_sentence_stream_signal.connect(self.accept_voice_message)

    def disconnect(self):
        response_to_user_message_sentence_stream_signal.disconnect(self.accept_voice_message)

    def cancel_speak(self) -> None:
        self.disconnect()
        if self.voice_service is None:
            return
        self.voice_service.stop()
