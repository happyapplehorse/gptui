from __future__ import annotations
import json
import logging
import sys
from abc import ABCMeta, abstractmethod
from importlib import import_module

import agere.commander as ac
import semantic_kernel as sk
from dotenv import dotenv_values
from semantic_kernel.connectors.ai.open_ai import OpenAITextCompletion
from semantic_kernel.orchestration.sk_context import SKContext
from semantic_kernel.orchestration.sk_function_base import SKFunctionBase

from .kernel_exceptions import (
    PluginInfoError,
    PluginsMatchError,
)
from .null_logger import get_null_logger


class KernelInterface(metaclass=ABCMeta):
    @property
    @abstractmethod
    def commander(self) -> ac.CommanderAsyncInterface:
        ...
    
    @commander.setter
    @abstractmethod
    def commander(self, commander: ac.CommanderAsyncInterface) -> None:
        ...
    
    @property
    @abstractmethod
    def sk_kernel(self) -> sk.Kernel:
        ...
    
    @sk_kernel.setter
    @abstractmethod
    def sk_kernel(self, sk_kernel: sk.Kernel) -> None:
        ...
    
    @abstractmethod
    def set_sk_kernel(self, sk_kernel: sk.Kernel, plugins_list: list[tuple]) -> None:
        ...
    
    @property
    @abstractmethod
    def functions_meta_in_kernel(self) -> dict:
        ...
    
    @property
    @abstractmethod
    def functions_link_in_kernel(self) -> dict:
        ...
    
    @property
    @abstractmethod
    def plugins_in_kernel(self) -> list[tuple]:
        ...
    
    @property
    @abstractmethod
    def llm_function_call(self) -> Kernel.LLM_Function_Call:
        ...

    @staticmethod
    @abstractmethod
    def make_basic_semantic_kernel(dot_env_config_path: str | None = None) -> sk.Kernel:
        ...

    @abstractmethod
    def make_commander(self, logger: logging.Logger | None = None) -> ac.CommanderAsyncInterface:
        ...

    @abstractmethod
    def add_plugins(self, plugins_list: list[tuple]) -> None:
        ...

    @abstractmethod
    def remove_plugins(self, plugins_list: list[tuple]) -> None:
        ...

    @abstractmethod
    def overwrite_plugins(self, plugins_list: list[tuple]) -> None:
        ...
    
    @abstractmethod
    def register_plugins(self, plugins_list: list[tuple]) -> None:
        ...

    @abstractmethod
    def context_render(self, args: dict, function: SKFunctionBase) -> SKContext:
        ...


class Kernel(KernelInterface):
    def __init__(self, dot_env_config_path: str | None = None, logger: logging.Logger | None = None):
        self.dot_env_config_path = dot_env_config_path
        self.logger = logger or get_null_logger()
        self._commander = self.make_commander(self.logger)
        self._sk_kernel = Kernel.make_basic_semantic_kernel(dot_env_config_path)
        self._llm_function_call = self.LLM_Function_Call(self)
        self._functions_meta_in_kernel = {}
        self._functions_link_in_kernel = {}
        self._plugins_in_kernel = []

    @property
    def commander(self) -> ac.CommanderAsyncInterface:
        return self._commander

    @commander.setter
    def commander(self, commander: ac.CommanderAsyncInterface) -> None:
        self._commander = commander

    @property
    def sk_kernel(self) -> sk.Kernel:
        return self._sk_kernel

    @sk_kernel.setter
    def sk_kernel(self, sk_kernel: sk.Kernel) -> None:
        try:
            self.set_sk_kernel(sk_kernel=sk_kernel, plugins_in_kernel=[])
        except PluginsMatchError:
            raise ValueError(
                "The kernel instance assigned to sk_kernel must be a kernel instance where the registered plugins are empty. "
                "If plugins are not empty, please use the set_sk_kernel method. "
                "It's recommended that all management of plugins be done through gk_kernel. "
            )

    def set_sk_kernel(self, sk_kernel: sk.Kernel, plugins_in_kernel: list[tuple] | None = None) -> None:
        plugins_in_kernel = plugins_in_kernel or []
        if self._dose_plugins_match_sk_kernel(sk_kernel=sk_kernel, plugins_list=plugins_in_kernel) is True:
            self._sk_kernel = sk_kernel
            self._plugins_in_kernel = plugins_in_kernel
        else:
            raise PluginsMatchError(sk_kernel, plugins_in_kernel)
    
    @property
    def llm_function_call(self) -> Kernel.LLM_Function_Call:
        return self._llm_function_call

    @property
    def functions_meta_in_kernel(self) -> dict:
        return self._functions_meta_in_kernel

    @property
    def functions_link_in_kernel(self) -> dict:
        return self._functions_link_in_kernel

    @property
    def plugins_in_kernel(self) -> list[tuple]:
        if self._dose_plugins_match_sk_kernel(sk_kernel=self.sk_kernel, plugins_list=self._plugins_in_kernel) is True:
            return self._plugins_in_kernel
        else:
            raise PluginsMatchError(self.sk_kernel, self._plugins_in_kernel)

    @staticmethod
    def make_basic_semantic_kernel(dot_env_config_path: str | None = None) -> sk.Kernel:
        dot_env_config_path = dot_env_config_path or '.env'
        dot_env_config = dotenv_values(dot_env_config_path)
        openai_key = dot_env_config.get("OPENAI_API_KEY", None)
        org_id = dot_env_config.get("OPENAI_ORG_ID", None)
        assert openai_key, f"OpenAI API key not found in {dot_env_config_path} file"
        kernel = sk.Kernel()
        kernel.add_text_completion_service(               # We are adding a text service
            "OpenAI_davinci",                         # The alias we can use in prompt templates' config.json
            OpenAITextCompletion(
                "text-davinci-003",                   # OpenAI Model Name
                openai_key,
                org_id,
            )
        )
        kernel.set_default_text_completion_service("OpenAI_davinci")
        return kernel

    def make_commander(self, logger: logging.Logger | None = None) -> ac.CommanderAsyncInterface:
        return ac.CommanderAsync(logger or get_null_logger())

    def add_plugins(self, plugins_list: list[tuple]) -> None:
        self.register_plugins(plugins_list)
    
    def remove_plugins(self, plugins_list: list[tuple]) -> None:
        new_plugins_list = [plugin for plugin in self.plugins_in_kernel if plugin not in plugins_list]
        self.set_sk_kernel(self.make_basic_semantic_kernel(self.dot_env_config_path))
        self.register_plugins(new_plugins_list)

    def overwrite_plugins(self, plugins_list: list[tuple]) -> None:
        self.set_sk_kernel(self.make_basic_semantic_kernel(self.dot_env_config_path))
        self.register_plugins(plugins_list)

    def register_plugins(
        self,
        plugins_list: list[tuple],
    ) -> None:
        """
        args:
            plugins_list: plugins to include
            [
                (plugin_path, plugin_name) for semantic plugin,
                (plugin_path, plugin_file, plugin_name) for natice plugin,
                    - it can also accept the initialization parameters of the class in the form of a tuple and a dictionary as the fourth and fifth optional parameters.
            ]
        """
        new_plugins_list = [plugin for plugin in plugins_list if plugin not in self.plugins_in_kernel]
        _, functions_meta_in_kernel, functions_link_in_kernel = register_plugins_to_sk_kernel(
            plugins_list=new_plugins_list,
            sk_kernel=self.sk_kernel,
        )

        # Refresh plugins_in_kernel, functions_link_in_kernel and functions_meta_in_kernel
        self._plugins_in_kernel.extend(new_plugins_list)
        self._functions_meta_in_kernel = functions_meta_in_kernel
        self._functions_link_in_kernel = functions_link_in_kernel

    def context_render(self, args: dict, function: SKFunctionBase) -> SKContext:
        context = self.sk_kernel.create_new_context()
        params = function.describe().parameters
        for param in params:
            name = param.name
            default_value = param.default_value
            context[name] = default_value
        for arg, value in args.items():
            context[arg] = value
        return context

    def _dose_plugins_match_sk_kernel(self, sk_kernel: sk.Kernel, plugins_list: list[tuple]) -> bool:
        """
        Check if the plugins in plugins_list is the same as the plugins in the kernel.
        """
        # Get all plugins' names in self.sk_kernel
        native_functions = sk_kernel.skills.get_functions_view().native_functions
        semantic_functions = sk_kernel.skills.get_functions_view().semantic_functions
        native_functions.update(semantic_functions)
        all_functions = native_functions
        skill_names = set(all_functions.keys())
        # Get all plugins' names in plugins_list
        plugin_names = set()
        for plugin in plugins_list:
            if len(plugin) == 2:
                plugin_names.add(plugin[1])
            elif len(plugin) >= 3:
                plugin_names.add(plugin[2])
        if plugin_names == skill_names:
            return True
        else:
            return False

    class LLM_Function_Call:
        def __init__(self, kenel: Kernel):
            self.kenel = kenel
        
        def sk_plugins_to_openai_functions(self, 
            plugins_list: list = [], 
            functions: list = [], 
            to_user: bool = True,
            auto_remove_input: bool = True
        ) -> tuple[list[dict], dict]:
            """Retrieve the meta and links of the specified function registered in the kernel for use in LLM function calls.
            If both plugins_list and functions are not specified, all functions registered in the kenel will be returned.
            
            Args:
                plugins_list: Add specified plugins
                functions: Add specified functions
                to_user: Add to user ability
                auto_remove_input: Automatically remove the 'input' arg from the args list, which is automatically added by 'sk_kernel'.
                    When the arg name has been specified, this 'input' arg is actually redundant and useless.
                    The conditions for automatically removing 'input' arg is:
                        There are more than two args in the args list.
                        The description of 'input' is empty.
            
            Return:
                (
                    available_functions_meta: list,
                    available_functions_link: dict,
                )
            """
            functions_meta = []
            all_functions_meta_in_kernel = self.kenel.functions_meta_in_kernel
            if plugins_list or functions:
                for function in all_functions_meta_in_kernel.values():
                    if isinstance(function, dict):
                        # function is not organized by plugins
                        if (function["parent"] in plugins_list) or (function["name"] in functions):
                            functions_meta.append(function)
                    elif isinstance(function, list):
                        # function is organized by plugins
                        function_list = function
                        for one_function_dict in function_list:
                            function = list(one_function_dict.values())[0]
                            if (function["parent"] in plugins_list) or (function["name"] in functions):
                                functions_meta.append(function)
            else:
                for function in all_functions_meta_in_kernel.values():
                    if isinstance(function, dict):
                        # function is not organized by plugins
                        functions_meta.append(function)
                    elif isinstance(function, list):
                        # function is organized by plugins
                        function_list = function
                        for one_function_dict in function_list:
                            function = list(one_function_dict.values())[0]
                            functions_meta.append(function)
            
            available_functions_meta = []
            available_functions_link = {}
            for function in functions_meta:
                available_functions_meta.append(
                    {
                        "type": "function",
                        "function": {
                            "name": function["name"],
                            "description": function["description"],
                            "parameters": {
                                "type": "object",
                                "properties": (parameters := {}),
                                "required": (required := []),
                            },
                        },
                    }
                )
                if to_user is True:
                    parameters["to_user"] = {
                        "type": "string",
                        "description": "The content paraphrased for the user. The content of this parameter can tell the user what you are about to do, or it can be an explanation of the behavior of the function calling. For example, 'I'm going to search the internet, please wait a moment.'",
                        }
                params_num = len(function["args"])
                for param_name, param in function["args"].items():
                    if auto_remove_input is True and params_num >= 2:
                        if param_name == "input" and not param["description"]:
                            continue
                    parameters[param_name] = {
                        "type": "string",
                        "description": param["description"]
                    }
                    if param["default_value"] is None:
                        required.append(param_name)

                available_functions_link[function["name"]] = self.kenel.functions_link_in_kernel[function["name"]]
                
            return available_functions_meta, available_functions_link


class PluginMeta:
    def __init__(self, plugin_info: tuple):
        self.plugin_info = plugin_info

    def is_semantic(self):
        if len(self.plugin_info) == 2:
            return True
        else:
            return False

    def is_native(self):
        if len(self.plugin_info) >= 3:
            return True
        else:
            return False

    @property
    def name(self) -> str:
        return self.plugin_info[1] if len(self.plugin_info) == 2 else self.plugin_info[2]
    
    @property
    def functions_list(self) -> list:
        out = []
        meta = self.functions_meta
        for _, value in meta.items():
            out.append(value["name"])
        return out

    @property
    def functions_meta(self) -> dict:
        meta = get_plugins_functions_info(plugins_list=[self.plugin_info])
        return meta


def register_plugins_to_sk_kernel(
    sk_kernel: sk.Kernel,
    plugins_list: list[tuple],
) -> tuple:
    """
    args:
        sk_kernel: register to this kernel
        plugins_list: plugins to include
            [
                (plugin_path, plugin_name) for semantic plugin,
                (plugin_path, plugin_file, plugin_name) for natice plugin:
                    - it can also accept the initialization parameters of the class in the form of a tuple and a dictionary as the fourth and fifth optional parameters.
            ]
    retrun:
        (
            sk_kernel: semantic_kernel.Kernel
            functions_meta_in_kernel: dict
            functions_link_in_kernel: dict
        )
    """

    with TemporarySysPath():
        # register plugin
        for plugin_info in plugins_list:
            if len(plugin_info) == 2:
                sk_kernel.import_semantic_skill_from_directory(plugin_info[0], plugin_info[1])
            elif len(plugin_info) >= 3:
                if plugin_info[0] not in sys.path:
                    sys.path.append(plugin_info[0])
                plugin_file = import_module(plugin_info[1])
                plugin = getattr(plugin_file, plugin_info[2])
                args = ()
                kwargs = {}
                if len(plugin_info) >= 4:
                    params = plugin_info[3:5]
                    for param in params:
                        if isinstance(param, tuple):
                            args = param
                        elif isinstance(param, dict):
                            kwargs = param
                        else:
                            raise PluginInfoError(plugin_info)
                sk_kernel.import_skill(plugin(*args, **kwargs), plugin_info[2])
            else:
                raise PluginInfoError(plugin_info)
    
    functions_meta_in_sk_kernel = get_functions_meta_in_sk_kernel(sk_kernel=sk_kernel)
    functions_link_in_sk_kernel = get_functions_link_in_sk_kernel(sk_kernel=sk_kernel)
    
    return sk_kernel, functions_meta_in_sk_kernel, functions_link_in_sk_kernel

def get_plugins_functions_info(
    plugins_list: list[tuple],
    functions: list | None = None,
    organize_by_plugins: bool = False,
) -> dict:
    """
    Retrieve functions infomation from plugins, it does not register these plugins into the existing kernel, but creates a new temporary kernel to handle this information.
    args:
        plugins_list {list[tuple]}: plugins to include
            [
                (plugin_path, plugin_name) for semantic plugin,
                (plugin_path, plugin_file, plugin_name) for natice plugin,
                    - it can also accept the initialization parameters of the class in the form of a tuple and a dictionary as the fourth and fifth optional parameters.
            ]
        functions {list | None}: function filter, only function in funtions is picked if it is specified
        organize_by_plugins {bool}: functions meta are organized by plugins
    retrun:
        functions_meta: dict
    """
    sk_kernel = sk.Kernel()
    result_tuple = register_plugins_to_sk_kernel(plugins_list=plugins_list, sk_kernel=sk_kernel)
    if functions is None and organize_by_plugins is False:
        return result_tuple[1]
    else:
        functions_meta = get_functions_meta_in_sk_kernel(sk_kernel=result_tuple[0], functions=functions, organize_by_plugins=organize_by_plugins)
        return functions_meta

def get_functions_meta_in_sk_kernel(
    sk_kernel: sk.Kernel,
    functions: list | None = None,
    organize_by_plugins: bool = False,
) -> dict:
    """
    args:
        sk_kernel: get available functions in this kernel
        functions: function filter, only function in funtions is picked if it is specified
        organize_by_plugins: functions are organized by plugins
    return:
        organize_by_plugins = False:
            {
                plugin_name.function_name: {    # plugin_name in key is necessary, because it's possible to have a same name function in different plugins
                    "name": function_name,
                    "description": function_description
                    "args": {
                        arg_name: {
                            "name": param_name
                            "description": param_description
                            "default_value": param_default_value ---- None for no default_value, means it is a necessary parameter. if default_value is None, it should be a str "None".
                        }
                    "parent": plugin
                    }
                }
            }
        organize_by_plugins = True:
            {
                plugin_name: {
                    [
                        {
                            plugin_name.function_name: {
                                "name": function_name,
                                "description": function_description
                                "args": {
                                    arg_name: {
                                        "name": param_name
                                        "description": param_description
                                        "default_value": param_default_value ---- None for no default_value, means it is a necessary parameter. if default_value is None, it should be a str "None".
                                    }
                                "parent": plugin
                                }
                            }
                        },
                    ]
                }
            }
    """

    kernel = sk_kernel

    # Get a dictionary of skill names to all native and semantic functions
    native_functions = kernel.skills.get_functions_view().native_functions
    semantic_functions = kernel.skills.get_functions_view().semantic_functions
    native_functions.update(semantic_functions)
    all_functions = native_functions

    # Create a mapping between all function names and their descriptions
    # and also a mapping between function names and their parameters
    skill_names = list(all_functions.keys())
    all_functions_descriptions_dict = {}
    all_functions_params_dict = {}
    all_functions_skill_dict = {}
    all_functions_name_dict = {}
    plugin_dict = {}

    for skill_name in skill_names:
        for func in all_functions[skill_name]:
            if functions is not None:
                if func.name not in functions:
                    continue
            key = skill_name + "." + func.name
            all_functions_descriptions_dict[key] = func.description
            all_functions_params_dict[key] = func.parameters
            all_functions_skill_dict[key] = skill_name
            all_functions_name_dict[key] = func.name

    # Create the [AVAILABLE FUNCTIONS] section of the prompt
    available_functions = {}
    for name in list(all_functions_descriptions_dict.keys()):
        available_functions[name] = {
            "name":all_functions_name_dict[name],
            "description":all_functions_descriptions_dict[name],
            "args":{},
            "parent":all_functions_skill_dict[name]
        }

        # Add the parameters for each function
        parameters = all_functions_params_dict[name]
        for param in parameters:
            if not param.description:
                param_description = ""
            else:
                param_description = param.description
            if not param.default_value:
                param_default_value = None
            else:
                param_default_value = param.default_value

            available_functions[name]["args"][param.name] = {}
            available_functions[name]["args"][param.name]["name"] = param.name
            available_functions[name]["args"][param.name]["description"] = param_description
            available_functions[name]["args"][param.name]["default_value"] = param_default_value
    
        if organize_by_plugins is True:
            skill_name = all_functions_skill_dict[name]
            if skill_name not in plugin_dict:
                plugin_dict[skill_name] = []
            plugin_dict[skill_name].append({name:available_functions[name]})
            
    if organize_by_plugins is True:
        return plugin_dict
    else:
        return available_functions

def get_functions_link_in_sk_kernel(sk_kernel: sk.Kernel, functions: list | None = None) -> dict:
    """
    args:
        sk_kernel: get available functions' links in this kernel
        functions: function filter, only function in funtions is picked if it is specified
    return:
        {
            function_name: function,
        }
    """

    # Get a dictionary of skill names to all native and semantic functions
    native_functions = sk_kernel.skills.get_functions_view().native_functions
    semantic_functions = sk_kernel.skills.get_functions_view().semantic_functions
    native_functions.update(semantic_functions)
    all_functions = native_functions

    # Create a mapping between all function names and functions
    skill_names = list(all_functions.keys())
    functions_link = {}

    for skill_name in skill_names:
        for func in all_functions[skill_name]:
            if functions is not None:
                if func.name not in functions:
                    continue
            key = func.name
            function_obj = sk_kernel.skills.get_function(skill_name, func.name)
            functions_link[key] = function_obj
    return functions_link

def to_json_string(input, ensure_ascii: bool = False, sort_keys: bool = True, indent: int = 4, separators = (',',':'), **kwargs):
    if not isinstance(input, str):
        input = json.dumps(input, ensure_ascii=ensure_ascii, sort_keys=sort_keys, indent=indent, separators=separators, **kwargs)
    return input
    
def pretty_dict(dict_object: dict|None) -> str:
    if dict_object is None:
        return ""
    return json.dumps(dict_object, ensure_ascii = False, sort_keys = True, indent = 4, separators = (',',':'))


class TemporarySysPath:
    def __enter__(self):
        self.original_sys_path = sys.path[:]
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.path = self.original_sys_path
