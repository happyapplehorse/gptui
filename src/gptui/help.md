# Hotkeys

Press `ESC`, `ctrl+[`, or `ctrl+/` to bring up the hotkey menu.

Direct hotkeys:
- ctrl+q: exit the program
- ctrl+n: open a new conversation
- ctrl+s: save the current conversation
- ctrl+r: delete the current conversation
- ctrl+o: toggle the monochrome theme
- ctrl+t: switch to assistant tube
- ctrl+g: switch to file tube
- ctrl+p: switch to plugins panel

# Dynamic commands

## set_chat_parameters

Set the OpenAI chat parameters.
Arguments are specified in dictionary form.

Commonly used parameters are:
  - model
  - stream
  - temperature
  - frequency_penalty
  - presence_penalty
  - max_tokens

## set_max_sending_tokens_ratio

Set the ratio number of sent tokens to the total token window.
Argument is a float number between 0 and 1.

# Custom plugins

You can specify the folder for your custom plugins in the configuration file,
which defaults to "~/.gptui/plugins".
GPTUI will automatically scan this folder to retrieve the plugins contained within it.
You can copy the files from this folder (https://github.com/happyapplehorse/gptui/tree/main/custom_plugin_examples)
to the custom plugin directory for testing purposes.

This program utilizes semantic-kernel type plugins. Before customizing your own plugins,
it is recommended to read: https://learn.microsoft.com/en-us/semantic-kernel/agents/plugins/?tabs=python

You can customize two types of plugins:
1. Native plugins. These require you to write your own code tools, providing functions
or methods to accomplish the task.
2. Semantic plugins. They are created through natural language, completing the required
functionality through descriptive prompts.

To create a native plugin, place your Python module in the plugin directory (default is ~/.gptui/plugins)
and use the sk_function decorator to decorate your function tools. For guidance on writing plugins,
see here: https://learn.microsoft.com/en-us/semantic-kernel/agents/plugins/using-the-kernelfunction-decorator?tabs=python

To create a semantic plugin, place your plugin folder in the plugin directory (default is ~/.gptui/plugins).
For guidance on writing plugins, see here: https://learn.microsoft.com/en-us/semantic-kernel/prompts/saving-prompts-as-files?tabs=python
