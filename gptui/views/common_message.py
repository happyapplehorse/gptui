from textual.message import Message


class CommonMessage(Message):
    def __init__(self, message_name: str, message_content) -> None:
        self.message_name = message_name
        self.message_content = message_content
        super().__init__()
