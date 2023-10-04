from typing import Any

from .driver_error import NoDriverError, NoDriverMethodError


class DriverInterface:

    def __init__(self, platform: str):
        self.platform = platform.lower()

    def __call__(self, *args, **kwargs) -> Any:
        method = getattr(self, self.platform, None)
        if method and callable(method):
            return method(*args, **kwargs)
        else:
            raise NoDriverError(self.platform)

    def termux(self):
        raise NoDriverMethodError(driver="termux", method=self.__class__.__name__)
    
    def linux(self):
        raise NoDriverMethodError(driver="linux", method=self.__class__.__name__)
    
    def macos(self):
        raise NoDriverMethodError(driver="macos", method=self.__class__.__name__)
    
    def windows(self):
        raise NoDriverMethodError(driver="windows", method=self.__class__.__name__)
