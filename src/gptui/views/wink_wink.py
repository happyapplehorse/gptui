import asyncio
import logging
from abc import ABC, abstractmethod

from rich.text import TextType


gptui_logger = logging.getLogger("gptui_logger")


class Happy(ABC):

    @abstractmethod
    def refresh(self, content, apple_width: int, apple_height: int) -> None:
        ...

    @property
    @abstractmethod
    def canvas_width(self) -> int:
        ...
    
    @property
    @abstractmethod
    def canvas_height(self) -> int:
        ...


class Apple(ABC):

    @abstractmethod
    def frame(self, inp) -> tuple[bool, tuple[float, TextType]]:
        ...

    @property
    @abstractmethod
    def canvas_width(self) -> int:
        ...
    
    @property
    @abstractmethod
    def canvas_height(self) -> int:
        ...


class Horse:
    def __init__(self):
        self.input = None
        self.happy = None
        self.apple = None
        self.run_status = False
        self._stop_flag = False
        self._stop_async_flag = False
        self._stop_async_event = asyncio.Event()

    def set_happy(self, happy: Happy) -> None:
        self.happy = happy

    def refresh_input(self, user_input: str) -> None:
        self.input = user_input
    
    def stop(self):
        self._stop_flag = True

    async def stop_async(self):
        if self.run_status is False:
            return
        self._stop_async_event.clear()
        self._stop_async_flag = True
        await self._stop_async_event.wait()

    async def run(self, apple: Apple, size_check: bool = True) -> bool:
        self.run_status = True
        assert self.happy is not None
        self._stop_flag = False
        self._stop_async_flag = False
        self.apple = apple
        if size_check:
            if (apple.canvas_width > self.happy.canvas_width) or (apple.canvas_height > self.happy.canvas_height):
                self.run_status = False
                return False
        
        status = True
        while status:
            inp = self.input
            self.input = None
            status, frame_info = apple.frame(inp)
            if self._stop_flag or self._stop_async_flag:
                break
            await self.frame_handle(frame_info)
        
        if self._stop_async_flag:
            self._stop_async_event.set()
        self.run_status = False
        return True

    async def frame_handle(self, frame_info: tuple[float, TextType] | None) -> None:
        if frame_info is None:
            return
        interval, frame = frame_info
        await asyncio.sleep(interval)
        self.happy_render(frame)

    def happy_render(self, content: TextType):
        assert self.happy is not None
        assert self.apple is not None
        self.happy.refresh(content, self.apple.canvas_width, self.apple.canvas_height)
