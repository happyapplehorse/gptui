from __future__ import annotations
from typing import Callable, TYPE_CHECKING


if TYPE_CHECKING:
    from .driver_interface import DriverInterface


class DriverError(Exception):
    ...


class NoDriverError(DriverError):
    def __init__(self, driver: str):
        self.driver = driver
    
    def __str__(self):
        return f"There is no {self.driver} driver."


class NoDriverMethodError(DriverError):
    def __init__(self, driver: str | Callable, method: str | DriverInterface):
        if isinstance(driver, str):
            self.driver = driver
        else:
            self.driver = driver.__name__
        if isinstance(method, str):
            self.method = method
        else:
            self.method = type(method).__name__
    
    def __str__(self):
        return f"There is no {self.method} method in {self.driver} driver."
