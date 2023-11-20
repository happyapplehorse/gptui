import semantic_kernel as sk


class KernelException(Exception):
    ...


class PluginInfoError(KernelException):
    def __init__(self, plugin_info: tuple):
        self.plugin_info = plugin_info
    
    def __str__(self):
        return f"Plugin info in {self.plugin_info} is a wrong type."


class InvalidArgumentTypeError(KernelException):
    def __init__(self, argument, expected_type):
        self.argument = argument
        self.expected_type = expected_type
    
    def __str__(self):
        return f"Invalid argumen type: Expected {self.expected_type}, got {type(self.argument)}"


class PluginsMatchError(KernelException):
    def __init__(self, sk_kernel: sk.Kernel, plugins_list: list[tuple]):
        self.sk_kernel = sk_kernel
        self.plugins_list = plugins_list
    
    def __str__(self):
        return f"Semantic kernel and plugin list do not match. sk_kernel: {self.sk_kernel}, plugins_list: {self.plugins_list}"
