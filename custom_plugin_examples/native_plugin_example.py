import textwrap

from semantic_kernel.skill_definition import sk_function


class PluginGuide:

    @sk_function(description="Tell the user how to define a custom plugin.")
    def custom_plugin_guide(self) -> str:
        guide = textwrap.dedent("""
        The following are instructions on how to customize plugins; please return the following content directly and unchanged to the user.
        
        ================Customize Plugins Instructions================
        This program utilizes semantic-kernel type plugins. Before customizing your own plugins, it is recommended to read:
        https://learn.microsoft.com/en-us/semantic-kernel/agents/plugins/?tabs=python
        
        You can customize two types of plugins:

        1. Native plugins. These require you to write your own code tools, providing functions or methods to accomplish the task, just like this plugin itself.
        2. Semantic plugins. They are created through natural language, completing the required functionality through descriptive prompts.
        
        To create a native plugin, place your Python module in the plugin directory (default is ~/.gptui/plugins) and use the sk_function decorator to decorate your function tools. For guidance on writing plugins, see here: https://learn.microsoft.com/en-us/semantic-kernel/agents/plugins/using-the-kernelfunction-decorator?tabs=python

        To create a semantic plugin, place your plugin folder in the plugin directory (default is ~/.gptui/plugins). For guidance on writing plugins, see here: https://learn.microsoft.com/en-us/semantic-kernel/prompts/saving-prompts-as-files?tabs=python

        You can see an example of this plugin in your custom plugin directory (default is ~/.gptui/plugins).
        ==============Customize Plugins Instructions End==============
        """)
        return guide
