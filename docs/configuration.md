## Configuration Guide

GPTUI offers a wide array of configurable options, utilizing the YAML file format.
To understand the basic syntax of YAML, you can visit [here](https://docs.ansible.com/ansible/latest/reference_appendices/YAMLSyntax.html).
The actual configuration options and default values adhere to the contents of the configuration file,
and this document might not be as current as the updates to the actual configuration file.

Within the configuration file, options that are commented out indicate that they have default configurations
and may not require modification. However, please note that when modifying the value of a list,
the list will be changed as a whole. This means you cannot override just a part of a list that has default configurations,
as this would clear the other options. For example, to set the status_region_default to “GPTUI Welcome",
given its following default configuration:
```
#tui_config:
#  conversations_recover: true
#  voice_switch: false
#  speak_switch: false
#  file_wrap_display: true
#  ai_care_switch: true
#  ai_care_depth: 2
#  ai_care_delay: 60
#  status_region_default:
#  waiting_receive_animation: "default"
```
You would need to modify the entire tui_config list to:
```
tui_config:
  conversations_recover: true
  voice_switch: false
  speak_switch: false
  file_wrap_display: true
  ai_care_switch: true
  ai_care_depth: 2
  ai_care_delay: 60
  status_region_default:
  waiting_receive_animation: "GPTUI Welcome"
```
Instead of this:
```
tui_config:
#  conversations_recover: true
#  voice_switch: false
#  speak_switch: false
#  file_wrap_display: true
#  ai_care_switch: true
#  ai_care_depth: 2
#  ai_care_delay: 60
#  status_region_default:
  waiting_receive_animation: "default"
```

## Resetting to Default Configuration

You can simply delete the configuration file, for instance `rm ~/.gptui/.config.yml`, and the program will automatically
re-download the default configuration file upon the next launch.
For the configuration file search strategy, refer to [here](https://github.com/happyapplehorse/gptui/blob/main/README.md#installation).

## Configuration Options

Currently, you can configure the following:

### GPTUI_BASIC_SERVICES_PATH

This is the directory for GPTUI's basic service components. It should not be changed without modifying the source code.

### PLUGIN_PATH

This is the path for GPTUI's built-in plugins. It should not be changed without modifying the source code.

### DEFAULT_PLUGIN_PATH

This is the path for GPTUI's built-in default plugins, which are not shown in the plugin list and are automatically activated.
It should not be changed without modifying the source code.

### custom_plugin_path

This is the directory for GPTUI's custom plugins and can be modified. The default value is `~/.gptui/plugins/`.

### dot_env_path

This setting specifies the path of the file configuring environment variables, where API keys are configured.
The default value is `~/.gptui/.env_gptui`.

### default_openai_parameters

This option is a dictionary used to specify default parameter configurations when using GPT for chatting.

### default_conversation_parameters

This option is a dictionary used to specify GPTUI's default conversation parameter settings.
- `max_sent_tokens_ratio`: A float value that sets the ratio of the maximum number of sent tokens to the
entire model token window. For instance, if the model's token window size is 1000, and this parameter is set to 0.6,
then when the chat context tokens to be sent exceed 600, it will automatically truncate to below 600.
The remaining 400 tokens will then serve as the window for the model's response tokens. This setting is crucial
as the model's token window is the sum of sent and received token numbers, and without this setting,
there's a risk that sent tokens might occupy too much context length, leading to the model being unable to
respond or providing incomplete responses.

### tui_config

This option is a dictionary used for configuring GPTUI's default settings.
- `conversations_recover`: A boolean value, sets the default state of GPTUI’s “Recovery” switch,
determining whether to automatically save and recover GPTUI's state.
- `voice_switch`: A boolean value, sets the default state of GPTUI’s “Voice” switch,
determining whether to enable the voice conversation feature.
- `speak_switch`: A boolean value, sets the default state of GPTUI’s “Speak” switch,
determining whether to enable the feature to read out response content.
- `file_wrap_display`: A boolean value, sets the default state of GPTUI’s “Fold File” switch,
determining whether to enable the automatic folding of file content into a file icon.
- `ai_care_switch`: A boolean value, sets the default state of GPTUI’s “AI-Care” switch,
determining whether to enable the AI-Care feature.
- `ai_care_depth`: An integer value, sets the maximum number of proactive speaking turns AI-Care can take
in the absence of user response.
- `ai_care_delay`: An integer value in seconds, sets the delay before AI-Care activates after a conversation finishes.
AI-Care will only kick in after this delay post a completed conversation.
- `status_region_default`: A string value, sets the default content displayed in the status region.
- `waiting_receive_animation`: A specific string type, sets the type of waiting animation. The default value is `“default”`.

### log_path

Sets the path for the log file. Default is `~/.gptui/logs.log`.

### workpath

Sets the working path for GPTUI. The default is `~/.gptui/user`, where default vector databases and temporary files,
among others, will be stored.

### directory_tree_path

The root directory of the filesystem that GPTUI can display. The default value is `~/`.
When importing and exporting files, GPTUI can only display files and folders under this directory.

### conversation_path

Sets the file path for exporting and importing GPTUI conversation records. The default value is `~/.gptui/user/conversations`.

### vector_memory_path

Sets the path for the vector database, the default being `~/.gptui/user/vector_memory_database`.

### terminal

Sets the terminal being used, with tested terminals including `termux`, `wezterm`.

### os

Sets the platform being used, offering four options:
- termux
- linux
- macos
- windows

Since termux is not a complete Linux system, it's treated as a separate option.

### default_plugins_used

This option is a list setting the default active state for plugins, including both built-in and custom plugins.

### location_city

Sets your geographical location to allow the LLM to access your location information.
This can be set to your city name or left unset.

### log_level

Sets the log printing level.

### openai_model_info

This option is a dictionary storing information for various models, with the model's tokens_window set here.
For example:
```
openai_model_info
  gpt-4-1106-preview:
    tokens_window: 128000
  gpt-4-0613:
    tokens_window: 8192
```
