# GPTUI
![GitHub](https://img.shields.io/github/license/happyapplehorse/gptui)
![PyPI - Version](https://img.shields.io/pypi/v/gptui)
[![GitHub Workflow Status (with event)](https://img.shields.io/github/actions/workflow/status/happyapplehorse/gptui/static.yml?label=docs)](https://happyapplehorse.github.io/gptui/)
![GitHub Workflow Status (with event)](https://img.shields.io/github/actions/workflow/status/happyapplehorse/gptui/python-publish.yml?label=build)

[English readme](README.md) • [简体中文 readme](README.zh.md)

<img src="https://github.com/happyapplehorse/happyapplehorse-assets/blob/main/imgs/gptui_logo.png" alt="gptui_logo" align="left" width="70px" height="70px"/>
GPTUI is a GPT conversational TUI (Textual User Interface) tool that runs within the terminal.
Using the Textual framework for its TUI interface and equipping the plugin framework provided by Semantic Kernel.
GPTUI offers a lightweight <a href="#gptui_kernel">Kernel</a> to power AI applications.
The top-level TUI application is decoupled from the underlying Kernel, allowing you to easily replace the TUI interface or expand its functionalities.
At present, only the GPT model of OpenAI is supported, and other LLM interfaces will be added later.

&nbsp;
![gptui_demo](https://github.com/happyapplehorse/happyapplehorse-assets/blob/main/imgs/gptui_demo.gif)

## TUI Features
- Create and manage conversations with GPT.
- Display context tokens in real-time.
- View and adjust GPT conversation parameters at any time, such as temperature, top_p, presence_penalty, etc.
- A dedicated channel to display internal process calls.
- Offers a file channel through which you can upload to or download from GPT.
- Voice functionality.
- Group talk functionality[^recommend_better_model][^token_cost].
- AI-Care. Your AI can propactively care for you[^ai_care].
- Optional plugin features, including (customizable, continuously being added and refined, some plugin prompts are still under development):
  - Internet search[^google_key].
  - Open interpreter[^open_interpreter][^token_cost][^recommend_better_model]. (Temporarily removed, waiting to be added back after it supports openai v1.x.)
  - Reminders[^recommend_better_model].
  - Recollecting memories from vectorized conversation history.

![gptui_img](https://github.com/happyapplehorse/happyapplehorse-assets/blob/main/imgs/gptui_img.jpg)

[^open_interpreter]: This plugin utilizes [open-interpreter](https://github.com/KillianLucas/open-interpreter), you need to
first follow the instructions provided by open-interpreter to properly set up the environment and API.
The open-interpreter has the permission to execute code, please ensure that you are already aware of the associated risk before
enabling this feature.
[^recommend_better_model]: It is recommended to use this under the GPT-4 model or a better one.
[^token_cost]: Note: This feature may incur a significant token cost.
[^ai_care]: Powered by [AI-Care](https://github.com/happyapplehorse/ai-care).
[^google_key]: `GOOGLE_KEY` and `GOOGLE_CX` are required. Obtained free from [here](https://developers.google.com/custom-search/v1/introduction).

# Compatibility
GPTUI runs in a command line environment and is compatible with Linux, macOS, Windows and Android[^compatibility].
Using the functionality provided by textual-web, you can also run GPTUI in the browser and share it with remote friends👍.

[^compatibility]: I haven't tested it on the Windows platform yet, and some functionalities like code copying,
voice features, etc., still need drivers to be written. I will complete these features later.
When running on Android, please use the [Termux](https://github.com/termux/termux-app) terminal tool.
For additional features like code copying and voice functionalities,
you need to install [Termux-API](https://github.com/termux/termux-api) and grant the necessary permissions.

<a name="gptui_kernel"> </a>
## ⚙️ GPTUI Kernel

GPTUI offers a lightweight Kernel for building AI applications, allowing you to easily expand GPTUI's capabilities or construct your own AI application.

<p align="center"><img src="https://github.com/happyapplehorse/happyapplehorse-assets/blob/main/imgs/gptui_framework.png" alt="gptui-framework" width="700"/></p >

The **kernel** relies on **jobs** and **handlers** to perform specific functions.
To achieve new functionalities, all you need to do is write or combine your own **jobs** and **handlers**.
The **manager** and **kernel** of GPTUI are entirely independent of the **client** application, enabling you to effortlessly relocate the **manager** or **kernel** for use elsewhere.
The application layer of GPTUI (**client**) employs the CVM architecture, where the model layer provides foundational, reusable modules for interaction with LLM, independent of specific views and controllers implementations.
If you wish to build your own AI application, you can start here, fully utilizing the **kernel**, **manager**, and models.
To alter or expand UI functionalities, typically, only modifications to the controllers and views are needed.

See Development Documentation for details. [Documentation](#documentation).

# Installation

Normal use requires ensuring stable network connection to OpenAI.
If you encounter any issues, please refer to [troubleshooting](docs/troubleshooting.md).

## Install with pip

```
pip install gptui
```

[Config your API keys](#config-api-keys) before running.

To run：
```
gptui
```
Specify config file：
```
gptui --config <your_config_file_path>
```
This program loads files through the following steps:
1. Read the configuration file from --config. If not specified, proceed to the next step.
2. Search for ~/.gitui/.config.yml in the user directory. If not found, move to the next step.
3. Copy the default configuration file gptui/config.yml to ~/.gitui/.config.yml and use it.

## Install from source

```
git clone https://github.com/happyapplehorse/gptui.git
cd gptui
pip install .
```
API configuration is required before running.

To run:

```bash
gptui
# Or you can also use
# python -m gptui
```

You can also directly run the startup script (this allows you to modify the source code and run it immediately):
First, install the dependencies:

```
pip install -r requirements.txt
```
Then, run the startup script:
```
python main.py
```

When running the program with `python main.py` or `python -m gptui`, use `gptui/config.yml` as the configuration file.

On Linux or macOS systems, if you want to use voice functionalities, you'll need to install pyaudio separately.

## Configuration

### Config API keys
Configure the corresponding API Keys in `~/.gptui/.env_gptui`.
Refer to the [.env_gptui.example](https://github.com/happyapplehorse/gptui/blob/main/.env_gptui.example) file.
When using the "WebServe" plugin, `GOOGLE_KEY` and `GOOGLE_CX` need to be provided, which can be [obtained](https://developers.google.com/custom-search/v1/introduction) free of charge from Google.

## Config File
See `./config.yml` for a config file example that lists all configurable options.
Depending on the platform you are using, it is best to configure the following options:

- os: system platform

Otherwise, some features may not work properly, such as code copy and voice related functions.


# Quick Start

## Interface Layout

![gptui-layout](https://github.com/happyapplehorse/happyapplehorse-assets/blob/main/imgs/gptui_layout.jpg)

- **chat area**: Display area for chat content.
- **status area**： Program status display area, displaying response animations and notifications.
- **input area**: Chat content input area.
- **auxiliary area**: Auxiliary information area, displaying "internal communication" between the program and the LLM, including function call information, etc.
- **control area**: The program's control area, where you can view and set the state of the program, such as change OpenAI chat parameters.
- **chat tabs**: Conversation Tab Bar.
- **conversation control**: Conversation control buttons. From top to bottom they are:
  - `+`: **_New conversation_**
  - `>`: **_Save conversation_**
  - `<`: **_Load conversation_**
  - `-`: **_Delete conversation_**
  - `x`: **_Delete conversation file_**
  - `n`: **_Disposable conversation_**
  - `↥`: **_Upload file_**
- **panel selector**: Panel selection area. From top to bottom they are：
  - `C`: **_Conversation file records_**
  - `D`: **_System file tree_**
  - `A`: **_Auxiliary information panel_**
  - `T`: **_File pipeline panel_**
  - `P`: **_Plugin selection panel_**
- **switches**：Direct control switches. From left to right they are：
  - `R`: **_Program state auto save and restore switch_**
  - `V`: **_Voice switch_**
  - `S`: **_Read reply by voice_**
  - `F`: **_Fold files in chat_**
  - `|Exit|`: **_Exit program_**
- **dashboard**：Context window size for chat.
- **others**:
  - `<`: **_Previous chat_**
  - `>`: **_Next chat_**
  - `1`: **_Number of chats_**
  - `☌`: **_[Running status](#Running status)_**
  - `↣`: **_Fold right non-chat area_**
  - `?`: **_Help documentation_**

## Running status

<span style="color:green">☌</span>: Ready.  
<span style="color:red">☍</span>: Task running.

## Dynamic Commands

Switch to `S` in the control area, enter the command and press enter. Currently supports the following commands:
- Set chat parameters
Command: **set_chat_parameters()**  
Parameters: OpenAI chat parameters in dictionary form, refer to [OpenAI Chat](https://platform.openai.com/docs/api-reference/chat/create).  
Example: `set_chat_parameters({"model": "gpt-4", "stream": True})`
- Set max sending tokens ratio
Command: **set_max_sending_tokens_ratio()**  
Parameters: The ratio of the number of sent tokens to the total token window, in float form. The remaining token count is used as the limit for the number of tokens GPT returns.  
Example: `set_max_sending_tokens_ratio(0.5)`

## Hotkeys

GPTUI provides hotkeys for commonly used features, see [Help](https://github.com/happyapplehorse/gptui/blob/main/docs/help.md).
In addition, you can also press `ESC`, `ctrl+[`, or `ctrl+/` to bring up the hotkey menu (this mode offers more comprehensive hotkey functionalities, but they are not exactly the same as the direct hotkeys.).

# Documentation

For detailed usage and development instructions, see [here](https://happyapplehorse.github.io/gptui/), for in-program help documentation see [here](src/gptui/help.md).

# Contribution

Some of GPTUI's plugin features rely on prompt, you can continue to help me improve these prompt.
And I'd like to have appropriate animation cues during certain state changes.
If you have any creative ideas, I'd appreciate your help in implementing them.
P.S.: Each contributor can leave a quote in the program.

# Note
This project utilizes OpenAI's Text-to-Speech (TTS) services for generating voice outputs.
Please be aware that the voices you hear are not produced by human speakers, but are synthesized by AI technology.

# License

GPTUI is built upon a multitude of outstanding open-source components and adheres to the [MIT License](https://github.com/happyapplehorse/gptui/blob/main/LICENSE) open-source agreement.
You are free to use it.
