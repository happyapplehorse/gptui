from __future__ import annotations
import inspect
import math
import logging
import time
import weakref
from abc import ABCMeta, abstractmethod
from typing import Literal, Iterable
from threading import Thread

from textual.message import Message

from ..utils.my_text import MyText as Text


gptui_logger = logging.getLogger("gptui_logger")


class Animation(metaclass=ABCMeta):
    animation_name: str
    @abstractmethod
    def run(self, animation_instance: AnimationManager.AnimationThread, message: AnimationRequest) -> None:
        ...


class AnimationRequest(Message):
    def __init__(
        self,
        ani_id,
        action: Literal["start", "end"],
        displayer: str = "default",
        priority: int = 2,
        ani_speed: float = 0.1,
        ani_type: str = "default",
        keep_time: float = 0,
        ani_end_display: str | Text = "recovery",
        others = None,
    ) -> None:
        """
        ani_end_display can be string or Text instance;
        if ani_end_display equals "default", it will display default content setted by AnimationManager
        if ani_end_display equals "recovery", it will display the erased content when animation started
        if others, it will be displayed directly.
        others for extended functions
        """
        self.ani_id = ani_id
        self.action = action
        self.displayer = displayer
        self.priority = priority
        self.ani_speed = ani_speed
        self.ani_type = ani_type
        self.keep_time = keep_time
        self.ani_end_display = ani_end_display
        self.others = others
        super().__init__()


def find_animations():
    current_module = inspect.getmodule(inspect.currentframe())
    animations = {}
    for _, obj in inspect.getmembers(current_module, predicate=inspect.isclass):
        if issubclass(obj, Animation) and not inspect.isabstract(obj):
            animations[obj.animation_name] = obj
    return animations


class AnimationManager:
    def __init__(self, displayer: dict, ani_end_display: str | Text = '', ani_links: dict | None = None):
        self.ani_id_dict = weakref.WeakValueDictionary()
        self.priority_dict = {}
        self.ani_links = ani_links or find_animations()
        self.displayer = displayer
        for key, _ in displayer.items():
            self.priority_dict[key] = weakref.WeakKeyDictionary()
        self.ani_end_display = ani_end_display

    def animation_start(self, message: AnimationRequest):
        animation_instance = self.AnimationThread(animation_manager=self, message=message)
        self.ani_id_dict[message.ani_id] = animation_instance
        animation_instance.start()

    def animation_end(self, ani_id) -> None:
        ani = self.ani_id_dict.get(ani_id)
        if ani:
            ani.end()

    def manage(self, message: AnimationRequest):
        if message.action == "start":
            self.animation_start(message)
        elif message.action == "end":
            self.animation_end(ani_id=message.ani_id)
    

    class AnimationThread(Thread):
        def __init__(self, animation_manager: AnimationManager, message: AnimationRequest) -> None:
            super().__init__()
            self.animation_status = True
            self.animation_manager = animation_manager
            self.message = message
            animation_manager.priority_dict[message.displayer][self] = message.priority

        def run(self) -> None:
            animation = self.animation_manager.ani_links.get(self.message.ani_type)
            if animation is None:
                raise ValueError(f"AnimationManager received a request for an animation type with no corresponding match. ani_type: {self.message.ani_type}")
            assert isinstance(animation, type(Animation))
            animation().run(animation_instance=self, message=self.message)

        def end(self) -> None:
            self.animation_status = False


def play_animation(
    animation_instance: AnimationManager.AnimationThread,
    message: AnimationRequest,
    keep_time,
    frames: Iterable,
    ) -> None:
    time_start = time.time()
    animation_manager = animation_instance.animation_manager
    display_object = animation_manager.displayer[message.displayer]
    if message.ani_end_display == "recovery":
        try:
            end_display = display_object.renderable
        except:
            end_display = animation_manager.ani_end_display
    elif message.ani_end_display == "default":
        end_display = animation_manager.ani_end_display
    else:
        end_display = message.ani_end_display
    while True:
        for frame in frames:
            if not animation_instance.animation_status or time.time() - time_start >= keep_time:
                display_object.update(end_display)
                return
            priority_list = animation_manager.priority_dict[message.displayer].values()
            if any(priority < message.priority for priority in priority_list):
                continue
            display_object.update(frame)
            time.sleep(message.ani_speed)


class DefaultAnimation(Animation):
    
    animation_name = "default"
    
    def run(
        self,
        animation_instance: AnimationManager.AnimationThread,
        message: AnimationRequest,
    ) -> None:
        frames_list = ["-- -- -- -- -- -- -- -- -- -- ", " -- -- -- -- -- -- -- -- -- --", "- -- -- -- -- -- -- -- -- -- -"]
        keep_time = message.keep_time or math.inf
        play_animation(
            animation_instance=animation_instance,
            message=message,
            keep_time=keep_time,
            frames=frames_list,
        )


class DefaultAnimation2(Animation):
    
    animation_name = "default_2"
    
    def run(
        self,
        animation_instance: AnimationManager.AnimationThread,
        message: AnimationRequest,
    ) -> None:
        frames_list = [
            "// // // // // // // // // // ",
            "// // // // // // // // // // ",
            " // // // // // // // // // //",
            " // // // // // // // // // //",
            "/ // // // // // // // // // /",
            "/ // // // // // // // // // /",
        ]
        keep_time = message.keep_time or math.inf
        play_animation(
            animation_instance=animation_instance,
            message=message,
            keep_time=keep_time,
            frames=frames_list,
        )


class DefaultAnimation3(Animation):
    
    animation_name = "default_3"
    
    def run(
        self,
        animation_instance: AnimationManager.AnimationThread,
        message: AnimationRequest,
    ) -> None:
        frames_list = [
            "|  |  |  |  |  |  |  |  |  |",
            " / |  |  |  |  |  |  |  |  |",
            "  __/ |  |  |  |  |  |  |  |",
            "  __ __/ |  |  |  |  |  |  |",
            "  __ __ __/ |  |  |  |  |  |",
            "  __ __ __ __/ |  |  |  |  |",
            "  __ __ __ __ __/ |  |  |  |",
            "  __ __ __ __ __ __/ |  |  |",
            "  __ __ __ __ __ __ __/ |  |",
            "  __ __ __ __ __ __ __ __/ |",
            "  __ __ __ __ __ __ __ __ __",
        ]
        keep_time = message.keep_time or math.inf
        play_animation(
            animation_instance=animation_instance,
            message=message,
            keep_time=keep_time,
            frames=frames_list,
        )


class StaticDisplayAnimation(Animation):
    
    animation_name = "static"
    
    def run(
        self,
        animation_instance: AnimationManager.AnimationThread,
        message: AnimationRequest,
    ) -> None:
        static_content = message.others
        keep_time = message.keep_time or 0
        frames_list = [static_content]
        play_animation(
            animation_instance=animation_instance,
            message=message,
            keep_time=keep_time,
            frames=frames_list,
        )


class SettingMemoryAnimation(Animation):
    
    animation_name = "setting_memory"
    
    def run(
        self,
        animation_instance: AnimationManager.AnimationThread,
        message: AnimationRequest,
    ) -> None:
        frames_list = [
                Text("Setting memory... -", "yellow"),
                Text("Setting memory... \\", "yellow"),
                Text("Setting memory... |", "yellow"),
                Text("Setting memory... /", "yellow"),
                ]
        play_animation(
            animation_instance=animation_instance,
            message=message,
            keep_time=math.inf,
            frames=frames_list,
        )
