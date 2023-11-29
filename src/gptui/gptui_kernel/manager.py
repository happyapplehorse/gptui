import os
import sys
import inspect
import logging
from abc import ABCMeta, abstractmethod
from importlib import import_module
from typing import Type

from agere.commander import Job

from .kernel import KernelInterface, Kernel, PluginMeta, TemporarySysPath
from .manager_exceptions import HandlerNotRegisterError, JobNotRegisterError
from .null_logger import get_null_logger


class ManagerInterface(metaclass=ABCMeta):
    @property
    @abstractmethod
    def gk_kernel(self) -> KernelInterface:
        ...

    @gk_kernel.setter
    @abstractmethod
    def gk_kernel(self, kernel: KernelInterface) -> None:
        ...

    @property
    @abstractmethod
    def services(self) -> KernelInterface:
        ...
    
    @services.setter
    @abstractmethod
    def services(self, kernel: KernelInterface) -> None:
        ...
    
    @property
    @abstractmethod
    def client(self) -> Type:
        ...

    @client.setter
    @abstractmethod
    def client(self, client) -> None:
        ...

    @property
    @abstractmethod
    def jobs(self) -> dict:
        ...

    @property
    @abstractmethod
    def handlers(self) -> dict:
        ...

    @staticmethod
    @abstractmethod
    def make_gk_kernel(dot_env_config_path: str | None = None, logger: logging.Logger | None = None) -> KernelInterface:
        ...

    @property
    @abstractmethod
    def available_functions_meta(self) -> list[dict]:
        ...

    @property
    @abstractmethod
    def available_functions_link(self) -> list[dict]:
        ...

    @abstractmethod
    def load_services(self, where, skill_name) -> None:
        ...

    @abstractmethod
    def register_jobs(self, module_name) -> None:
        ...

    @abstractmethod
    def register_handlers(self, module_name) -> None:
        ...

    @abstractmethod
    def get_job(self, job: str) -> Type:
        ...

    @abstractmethod
    def get_handler(self, handler: str) -> Type:
        ...

    @abstractmethod
    def add_plugins(self, plugins: list[tuple] | tuple) -> None:
        ...

    @abstractmethod
    def remove_plugins(self, plugins: list[tuple] | tuple) -> None:
        ...

    @abstractmethod
    def overwrite_plugins(self, plugins: list[tuple] | tuple) -> None:
        ...

    @abstractmethod
    def scan_plugins(self, path) -> tuple[list, list]:
        ...

    @property
    @abstractmethod
    def dot_env_config_path(self) -> str | None:
        ...


class Manager(ManagerInterface):
    def __init__(
        self,
        client,
        kernel: KernelInterface | None = None,
        service_kernel: KernelInterface | None = None,
        dot_env_config_path: str | None = None,
        logger: logging.Logger | None = None
    ):
        self._dot_env_config_path = dot_env_config_path
        self.logger = logger or get_null_logger()
        self._gk_kernel = kernel or Kernel(dot_env_config_path=dot_env_config_path, logger=self.logger)
        self._services = service_kernel or Kernel(dot_env_config_path=dot_env_config_path, logger=self.logger)
        self._client = client
        self._jobs = {}
        self._handlers = {}

    @property
    def dot_env_config_path(self) -> str | None:
        return self._dot_env_config_path

    @property
    def gk_kernel(self) -> KernelInterface:
        return self._gk_kernel
    
    @gk_kernel.setter
    def gk_kernel(self, kernel: KernelInterface) -> None:
        self._gk_kernel = kernel

    @property
    def services(self) -> KernelInterface:
        return self._services

    @services.setter
    def services(self, service_kernel: KernelInterface) -> None:
        self._services = service_kernel

    @property
    def client(self):
        return self._client

    @client.setter
    def client(self, client_) -> None:
        self.client = client_

    @property
    def jobs(self) -> dict:
        return self._jobs

    @property
    def handlers(self) -> dict:
        return self._handlers

    @staticmethod
    def make_gk_kernel(dot_env_config_path: str | None = None, logger: logging.Logger | None = None) -> KernelInterface:
        return Kernel(dot_env_config_path=dot_env_config_path, logger=logger)
    
    @property
    def available_functions_meta(self) -> list[dict]:
        meta, _ = self.gk_kernel.llm_function_call.sk_plugins_to_openai_functions()
        return meta

    @property
    def available_functions_link(self) -> dict:
        _, link = self.gk_kernel.llm_function_call.sk_plugins_to_openai_functions()
        return link

    def load_services(self, where, skill_name) -> None:
        if isinstance(where, str):
            self.services.sk_kernel.import_semantic_skill_from_directory(where, skill_name)
        else:
            self.services.sk_kernel.import_skill(where, skill_name=skill_name)

    def register_jobs(self, module_name) -> None:
        module = import_module(module_name)
        for name, obj in inspect.getmembers(module):
            if inspect.isclass(obj) or inspect.isfunction(obj):
                self._jobs[name] = obj

    def register_handlers(self, module_name) -> None:
        module = import_module(module_name)
        for name, obj in inspect.getmembers(module):
            if inspect.isclass(obj) or inspect.isfunction(obj):
                self._handlers[name] = obj

    def get_handler(self, handler: str):
        try:
            aim_handler = self.handlers[handler]
        except KeyError:
            raise HandlerNotRegisterError(handler=handler, manager=self)
        return aim_handler

    def get_job(self, job: str) -> Job:
        try:
            aim_job = self.jobs[job]
        except KeyError:
            raise JobNotRegisterError(job=job, manager=self)
        return aim_job
    
    def add_plugins(self, plugins: list[tuple] | tuple) -> None:
        if isinstance(plugins, tuple):
            plugins_list = [plugins]
        else:
            plugins_list = plugins
        self.gk_kernel.add_plugins(plugins_list)
    
    def remove_plugins(self, plugins: list[tuple] | tuple) -> None:
        if isinstance(plugins, tuple):
            plugins_list = [plugins]
        else:
            plugins_list = plugins
        self.gk_kernel.remove_plugins(plugins_list)

    def overwrite_plugins(self, plugins: list[tuple] | tuple) -> None:
        if isinstance(plugins, tuple):
            plugins_list = [plugins]
        else:
            plugins_list = plugins
        self.gk_kernel.overwrite_plugins(plugins_list)

    def scan_plugins(self, path) -> tuple[list, list]:
        children = os.listdir(path)
        dirs = [d for d in children if os.path.isdir(os.path.join(path, d))]
        files = [os.path.splitext(f)[0] for f in children if os.path.isfile(os.path.join(path, f))]
        
        def check_semantic_plugin(dir_path: str) -> bool:
            children = os.listdir(dir_path)
            dirs = [d for d in children if os.path.isdir(os.path.join(dir_path, d))]
            for dir in dirs:
                contents = os.listdir(os.path.join(dir_path, dir))
                files = [f for f in contents if os.path.isfile(os.path.join(dir_path, dir, f))]
                if {"skprompt.txt", "config.json"}.issubset(set(files)):
                    return True
            return False

        semantic_plugins_info_list = [(path, plugin_name) for plugin_name in dirs if check_semantic_plugin(os.path.join(path, plugin_name))]
        semantic_plugins_list = [PluginMeta(plugin_info) for plugin_info in semantic_plugins_info_list]

        with TemporarySysPath():
            if path not in sys.path:
                sys.path.append(path)
            native_plugins_list = []
            for file in files:
                module = import_module(file)
                for name, obj in inspect.getmembers(module):
                    if inspect.isclass(obj) and obj.__module__ == module.__name__:
                        params = self._check_auto_init_params(obj)
                        if params is None:
                            native_plugins_list.append(PluginMeta((path, file, name)))
                        else:
                            native_plugins_list.append(PluginMeta((path, file, name, params)))
        
        return semantic_plugins_list, native_plugins_list

    def _check_auto_init_params(self, plugin_class) -> tuple | None:
        params = None
        for _, method in plugin_class.__dict__.items():
            if hasattr(method, "_auto_init_params_") and method._auto_init_params_ is True:
                mode = method._auto_init_params_mode_
                if not isinstance(method, classmethod):
                    raise TypeError(f"{method} is not a classmethod.")
                if mode == "0":
                    params = method.__func__(plugin_class, self)
                else:
                    raise ValueError(f"Get error _auto_init_params_mode_: {mode}.")
        return params

def auto_init_params(mode: str = "0"):
    """
    Decorator:
        Mark the method for automatically obtaining initialization parameters,
        and set the mode of the callback parameter for this method.
        Currently, only mode "0" is supported, which requires the "manager" to return itself.
        It should be used outer of @classmethod.
    Usage:
        @auto_init_params("0")
        @classmethod
        def get_init_params(cls, manager) -> tuple:
            ...
    """
    def decorator(func):
        func._auto_init_params_ = True
        func._auto_init_params_mode_ = mode
        return func
    return decorator
