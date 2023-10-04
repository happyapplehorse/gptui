import semantic_kernel as sk


class KernelError(Exception):
    ...


class NoCommanderError(KernelError):
    def __init__(self, job):
        self.job = job
    
    def __str__(self):
        return f"Commander not found in {self.job}."


class NotTaskerError(KernelError):
    def __init__(self, job):
        self.job = job
    
    def __str__(self):
        return f"Task method of {self.job} is not a Tasker."


class NotHandlerError(KernelError):
    def __init__(self, job):
        self.job = job
    
    def __str__(self):
        return f"Object is not a Handler called in {self.job}."


class PluginInfoError(KernelError):
    def __init__(self, plugin_info: tuple):
        self.plugin_info = plugin_info
    
    def __str__(self):
        return f"Plugin info in {self.plugin_info} is a wrong type."


class InvalidArgumentTypeError(KernelError):
    def __init__(self, argument, expected_type):
        self.argument = argument
        self.expected_type = expected_type
    
    def __str__(self):
        return f"Invalid argumen type: Expected {self.expected_type}, got {type(self.argument)}"


class AttributeNotSetError(KernelError):
    def __init__(self, obj, attr):
        self.obj = obj
        self.attr = attr
    
    def __str__(self):
        return f"The {self.attr} attribute of {self.obj} has not been set yet."


class PluginsMatchError(KernelError):
    def __init__(self, sk_kernel: sk.Kernel, plugins_list: list[tuple]):
        self.sk_kernel = sk_kernel
        self.plugins_list = plugins_list
    
    def __str__(self):
        return f"Semantic kernel and plugin list do not match. sk_kernel: {self.sk_kernel}, plugins_list: {self.plugins_list}"
