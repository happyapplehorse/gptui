# GPTUI
![GitHub](https://img.shields.io/github/license/happyapplehorse/gptui)
![PyPI - Version](https://img.shields.io/pypi/v/gptui)
[![GitHub Workflow Status (with event)](https://img.shields.io/github/actions/workflow/status/happyapplehorse/gptui/static.yml?label=docs)](https://happyapplehorse.github.io/gptui/)
![GitHub Workflow Status (with event)](https://img.shields.io/github/actions/workflow/status/happyapplehorse/gptui/python-publish.yml?label=build)
[![Static Badge](https://img.shields.io/badge/bilibili-twototoo222-pink)](https://space.bilibili.com/80170263)

[English readme](README.md) • [简体中文 readme](README.zh.md)

<img src="https://github.com/happyapplehorse/happyapplehorse-assets/blob/main/imgs/gptui_logo.png" alt="gptui_logo" align="left" width="70px" height="70px"/>
GPTUI是一个在终端中运行的GPT对话TUI工具。
你可以使用快捷键高效掌控你的节奏。
GPTUI使用Textual构建TUI界面，使用Semantic Kernel提供的插件框架；您可以快速灵活地为自己的需求自定义插件。
GPTUI提供了一个轻量级的<a href=" ">Kernel</a >，用以驱动AI应用。上层的TUI应用与下层的Kernel解耦，使您可以轻松替换TUI界面或拓展其它功能。如果您喜欢，您也可以在此Kenrel上开发您自己的AI应用。
目前仅支持OpenAI的GPT模型，后续会增加对其它大语言模型接口的支持。

&nbsp;
![gptui_demo](https://github.com/happyapplehorse/happyapplehorse-assets/blob/main/imgs/gptui_demo.gif)

## TUI功能
- 创建并管理与GPT的对话。
- 实时显示上下文tokens窗口。
- 查看并随时设置与GPT对话的参数，例如temperature、top_p、presence_penalty等。
- 专门的通道显示内部过程调用。
- 提供一个文件通道，您可以通过此通道给GPT上传文件或下载文件。
- 语音功能。
- 群聊功能[^recommend_better_model][^token_cost]。
- AI-Care。你的AI可以主动关心你[^ai_care]。
- 可选的插件功能，包括（持续增加与优化中）：
  - 搜索互联网[^google_key]。
  - open interpreter[^open_interpreter][^token_cost][^recommend_better_model]。（暂时被移除，等待它支持openai v1.x后再被添加回来。）
  - 提醒[^recommend_better_model]。
  - 从矢量化的对话历史记录中回想记忆。
- 支持自定义插件。

![gptui_img](https://github.com/happyapplehorse/happyapplehorse-assets/blob/main/imgs/gptui_img.jpg)

[^open_interpreter]: 本插件使用了[open-interpreter](https://github.com/KillianLucas/open-interpreter) ，
需要先按open-interpreter的说明配置好open-interpreter的环境和API。
Open-interpreter具有执行代码的权限，在开启此功能前请确保你已经了解其中的风险。
[^recommend_better_model]: 推荐使用GPT-4或更好的模型。
[^token_cost]: 注意：该功能可能产生较多的tokens花费。
[^ai_care]: 由[AI-Care](https://github.com/happyapplehorse/ai-care)提供该能力。
[^google_key]: 需要提供`GOOGLE_KEY`和`GOOGLE_CX`。可以从[这里](https://developers.google.com/custom-search/v1/introduction)免费获取。

## 🎬 演示视频
- [AI-Care](https://www.bilibili.com/video/BV1ka4y1B7tQ)
- [界面和功能介绍](https://www.bilibili.com/video/BV18T4y1W7eg)

# 兼容性

GPTUI在命令行环境下运行，支持Linux，macOS，Windows和Android平台[^compatibility]。
使用textual-web提供的功能，您还可以在浏览器中运行GPTUI，并分享给远方的好友，不需要对方做任何的准备，也不需要对方具有API Key，只要有网络和浏览器即可👍。

[^compatibility]: Windows平台我还没有测试，部分功能的驱动还没有写，例如代码复制，语音功能等，后续会完善相关功能。
在Android上运行时，请使用[Termux](https://github.com/termux/termux-app)终端工具，部分拓展功能例如代码复制和语音功能需要安装[Termux-API](https://github.com/termux/termux-api)并赋予权限。

<a name="gptui_kernel"> </a >
## ⚙️ GPTUI Kernel

GPTUI提供了轻量级的构建AI应用的Kernel，使您可以方便地拓展GPTUI的功能或构建自己的AI应用。

<p align="center"><img src="https://github.com/happyapplehorse/happyapplehorse-assets/blob/main/imgs/gptui_framework.png" alt="gptui-framework" width="700"/></p >

**kernel**依赖于**jobs**和**handlers**实现具体的功能。要实现新的功能，您只需编写或组合自己的**jobs**与**handlers**。
GPTUI的**manger**和**kernel**完全不依赖于**client**应用，您可以轻松地将**manger**或**kernel**转移到别的地方使用。GPTUI的应用层（**client**）采用CVM架构，其中model层提供了基础的可重复使用的与LLM交互的功能模块，不依赖于views和controllers的具体实现，若要构件自己的AI应用，您可以从这里开始，完全复用**kernel**、**manger**以及models，若要更换或拓展UI功能，通常您只需要修改controllers以及views。
详请参考[开发文档](#文档)

如果需要用到gptui的部分组件或功能，你可以把gptui当作一个库来导入并使用。

# 安装

正常使用需要确保网络畅通，可以连接OpenAI。
如果遇到安装问题，请参考[troubleshooting](docs/troubleshooting.md)。

## 使用pip安装

```
pip install gptui
```
在运行之前您需要[配置API](#api-keys的配置)。
运行：
```
gptui
```
指定配置文件：
```
gptui --config <your_config_file_path>
```
本程序通过以下步骤加载文件：
1. 从`--config`中读取配置文件，如果没有指定，则进行下一步。
2. 从用户目录寻找`~/.gptui/.config.yml`，如果没有，则进行下一步。
3. 拷贝默认的配置文件`gptui/config.yml`到`~/.gitui/.config.yml`并使用。

## 从源码安装

```
git clone https://github.com/happyapplehorse/gptui.git
cd gptui
pip install .
```
在运行之前需要[配置API](#api-keys的配置)。
运行：
```
gptui
# 或者您也可以
# python -m gptui
```

您还可以直接运行启动脚本（这样允许您修改源代码并即刻运行）：
首先，安装依赖：
```
pip install -r requirements.txt
```
然后，运行启动脚本：
```
python main.py
```
当使用`python main.py`或`python -m gptui`来运行本程序时，使用`gptui/config.yml`作为配置文件。
在Linux或macOS系统下，如果要使用语音功能，还需要额外安装pyaudio。

# 配置

## API keys的配置

在`~/.gptui/.env_gptui`中配置相应的API Keys。参考[.env_gptui.example](https://github.com/happyapplehorse/gptui/blob/main/.env_gptui.example)文件。当使用“WebServe”插件时，需提供`GOOGLE_KEY`和`GOOGLE_CX`，它们可免费地从谷歌[获取](https://developers.google.com/custom-search/v1/introduction)。

## 配置文件

配置文件的示例请参考`./config.yml`，其中列出了所有可配置的选项。
根据您所使用的平台，最好配置以下选项：

- os: 系统平台

否则，部分功能可能不能正常使用，比如复制代码与语音相关功能。

## 配置指南

详细的配置说明请查看[这里](./docs/configuration.zh.md)。

# 快速开始

## 界面区域

![gptui-layout](https://github.com/happyapplehorse/happyapplehorse-assets/blob/main/imgs/gptui_layout.jpg)

- **chat area**: 聊天内容的显示区域。
- **status area**： 程序状态显示区域。显示响应动画以及通知等。
- **input area**: 聊天内容的输入区域。
- **auxiliary area**: 辅助信息区域，显示程序内部与LLM的“内部交流”，包括函数调用信息等。
- **control area**: 程序的控制区，在这里可以显示和设置程序的状态，例如动态地控制OpenAI的聊天参数。
- **chat tabs**: 对话标签页。
- **conversation control**: 对话的控制按钮。从上到下依次为：
  - `+`: **_新建对话_**
  - `>`: **_保存对话_**
  - `<`: **_载入对话_**
  - `-`: **_删除对话_**
  - `x`: **_删除对话文件_**
  - `n`: **_新建一次性对话_**
  - `↥`: **_上传文件_**。
- **panel selector**: 面板选择区域。从上到下依次为：
  - `C`: **_对话的文件记录_**。
  - `D`: **_系统文件树_**。
  - `A`: **_辅助信息面板_**。
  - `T`: **_文件管道面板_**。
  - `P`: **_插件选择面板_**。
- **switches**：直接控制开关。从左到右依次为：
  - `R`: **_程序状态自动保存与恢复开关_**。
  - `V`: **_语音开关_**。
  - `S`: **_语音朗读回复开关_**。
  - `F`: **_折叠聊天中的文件_**。
  - `|Exit|`: **_退出程序_**。
- **dashboard**：聊天的上下文窗口的大小。
- **others**:
  - `<`: **_前一个聊天_**。
  - `>`: **_后一个聊天_**。
  - `1`: **_聊天的数量_**。
  - `☌`: **_[运行状态](#运行状态提示)_**。
  - `↣`: **_折叠右侧非聊天区_**。
  - `?`: **_帮助文档_**。

## 运行状态提示
<span style="color:green">☌</span>: 就绪状态。  
<span style="color:red">☍</span>：有任务正在运行。

## 动态命令

在control area中切换到`S`，输入命令后回车。目前支持以下命令：
- 设置聊天参数
 命令：**set_chat_parameters()**  
 参数：字典形式的OpenAI聊天参数，参考[OpenAI Chat](https://platform.openai.com/docs/api-reference/chat/create)。  
 示例：`set_chat_parameters({"model": "gpt-4", "stream": True})`
- 设置最大发送token数量的比例
命令：**set_max_sending_tokens_ratio()**  
参数：发送token数量占总的token窗口的比例，float的形式。剩余的token数量作为GPT返回token数的限制。  
示例：`set_max_sending_tokens_ratio(0.5)`

## 快捷键

GPTUI为常用功能提供了快捷键，参考[帮助](https://github.com/happyapplehorse/gptui/blob/main/docs/help.md)。
另外，您还可以按`ESC`，`ctrl+[`或者`ctrl+/`来呼出快捷键菜单（此种方式的快捷键功能更全，但与直接的快捷键键位并不完全一致.）。

# 文档

详细使用和开发说明请看[这里](https://happyapplehorse.github.io/gptui/)，程序内的帮助文档看[这里](src/gptui/help.md)。

# 贡献

GPTUI的部分插件功能需要依靠提示词，您可以继续帮助我完善这些提示词。
我希望在一些状态变化时，有合适的动画提示，如果您有好的创意，欢迎帮我实现它。
每个贡献者可以在程序中留下一条语录。

# 注意

本项目使用OpenAI的文本转语音（TTS）服务来生成语音输出
请注意，您听到的声音不是由真人发出的，而是由人工智能技术合成的。

# License

GPTUI 建立在众多优秀的开源组件基础之上，遵循和使用 [MIT License](https://github.com/happyapplehorse/gptui/blob/main/LICENSE) 开源协议，您可以自由地使用。
