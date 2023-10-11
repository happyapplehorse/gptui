# GPTUI

[English readme](https://github.com/happyapplehorse/gptui/main/README.md) • [简体中文 readme](https://github.com/happyapplehorse/gptui/main/README.zh.md)

![gptui_demo](https://github.com/happyapplehorse/gptui-assets/blob/main/imgs/gptui_demo.gif)

GPTUI is a GPT conversational TUI (Textual User Interface) tool that runs within the terminal.
Using the Textual framework for its TUI interface and equipping the plugin framework provided by Semantic Kernel.
GPTUI offers a lightweight [Kernel](# GPTUI Kernel) to power AI applications. The top-level TUI application is decoupled from the underlying Kernel, allowing you to easily replace the TUI interface or expand its functionalities.
At present, only the GPT model of OpenAI is supported, and other LLM interfaces will be added later.

## TUI Features
-  Create and manage conversations with GPT.
-  Display context tokens in real-time.
-  View and adjust GPT conversation parameters at any time, such as temperature, top_p, presence_penalty, etc.
-  A dedicated channel to display internal process calls.
-  Offers a file channel through which you can upload to or download from GPT.
- Optional plugin features, including (customizable, continuously being added and refined, some plugin prompts are still under development):
  -  Internet search.
  -  Open interpreter.
  -  Reminders.
  -  Recollecting memories from vectorized conversation history.

# Compatibility
GPTUI runs in a command line environment and is compatible with Linux, macOS, Android, and of course Windows (I haven't tested it yet!). 
Using the functionality provided by textual-web, you can also run GPTUI in the browser and share it with remote friends.

## ⚙️ GPTUI Kernel


GPTUI offers a lightweight Kernel for building AI applications, allowing you to easily expand GPTUI's capabilities or construct your own AI application.
![gptui-framework](https://github.com/happyapplehorse/gptui-assets/blob/main/imgs/gptui_framework.png)
The **kernel** relies on **jobs** and **handlers** to perform specific functions. To achieve new functionalities, all you need to do is write or combine your own **jobs** and **handlers**.
The **manager** and **kernel** of GPTUI are entirely independent of the **client** application, enabling you to effortlessly relocate the **manager** or **kernel** for use elsewhere. The application layer of GPTUI (**client**) employs the CVM architecture, where the model layer provides foundational, reusable modules for interaction with LLM, independent of specific views and controllers implementations. If you wish to build your own AI application, you can start here, fully utilizing the **kernel**, **manager**, and models. To alter or expand UI functionalities, typically, only modifications to the controllers and views are needed.

See Development Documentation for details. [Developer Documentation](#Developer Documentation).

# Installation

Normal use requires ensuring stable network connection to OpenAI.

## Install with pip

(Will be uploaded to pypi soon!)

```
pip install xxx
```

[Config your API keys](# Config API keys).

Run：
```
gptui
```
Specify config file：
```
gptui --config your_config_file_path
```
This program loads files through the following steps:

1.Read the configuration file from --config. If not specified, proceed to the next step.
2.Search for ~/.gitui_config.yml in the user directory. If not found, move to the next step.
3.Copy the default configuration file ./config.yml to ~/.gitui_config.yml and use it.


## Run from source

```
git clone ...
cd gptui
pip install -r requirements.txt
```
On Linux or macOS systems, if you want to use voice and TTS (TextToSpeak) features, you'll also need to install pyaudio and espeak separately (currently, this is the only method provided, and the performance is not optimal).

[Config your API keys](# Config API keys).

Run：
```
python main.py
```
When running the program directly from the script, use ./config.yml as the config file.

## Configuration

### Config API keys
Configure the corresponding API Keys in `~/.gptui/.env_gptui`. Refer to the [.env_gptui.example](https://github.com/happyapplehorse/gptui/blob/main/.env_gptui.example) file. When using the "WebServe" plugin, `GOOGLE_KEY` and `GOOGLE_CX` need to be provided, which can be obtained free of charge from Google.

##Config File
See `./config.yml` for a config file example that lists all configurable options.
Depending on the platform you are using, it is best to configure the following options:

- os: system platform

Otherwise, some features may not work properly, such as code copy and voice related functions.


# Quick Start

## Interface Layout

![gptui-layout](https://github.com/happyapplehorse/gptui-assets/blob/main/imgs/gptui_layout.jpg)

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

GPTUI provides hotkeys for commonly used features, see [Help](https://github.com/happyapplehorse/gptui/blob/main/docs/help.md). In addition, you can also press `ESC` or `ctrl+[` to bring up the hotkey menu (this type of shortcut keys is not completely consistent with the direct hotkeys!).


# Documentation

For detailed instructions, see [here](docs/man.md), for in-program help documentation see [here](src/gptui/help.md), for further development, see [here](docs/development.md).

# Contribution

Some of GPTUI's plugin features rely on prompt, you can continue to help me improve these prompt. And I'd like to have appropriate animation cues during certain state changes. If you have any creative ideas, I'd appreciate your help in implementing them.
P.S.: Each contributor can leave a quote in the program.


# License

GPTUI is built upon a multitude of outstanding open-source components and adheres to the [MIT License](https://github.com/happyapplehorse/gptui/blob/main/LICENSE) open-source agreement. You are free to use it.
