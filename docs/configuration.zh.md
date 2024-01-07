## 配置说明
GPTUI提供了丰富的可配置选项，使用yaml文件格式进行配置。要了解yaml格式的基本语法，可以看[这里](https://docs.ansible.com/ansible/latest/reference_appendices/YAMLSyntax.html)。
实际的配置选项和默认值以配置文件中的内容为准，此文档可能会落后于实际配置文件的更新。

在配置文件中，被注释掉的配置项表明该配置项拥有默认配置，可以不用配置。
但请注意，当修改一个列表的值时，列表将作为一个整体被修改，也就是说不能单独覆盖一个具有默认配置的列表的一部分，因为这样会将其它的选项清除。
例如，要将status_region_default设置为“GPTUI Welcome"，由于它具有以下的默认配置：
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
你需要将整个tui_config列表修改为：
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
而不能是这样：
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

## 恢复默认配置
你可以直接删除配置文件，例如`rm ~/.gptui/.config.yml`，程序将在下次启动时自动重新下载默认的配置文件。配置文件查找策略请参考[这里](https://github.com/happyapplehorse/gptui/blob/main/README.zh.md#使用pip安装)。

## 配置选项
目前，你可以进行以下配置：

### GPTUI_BASIC_SERVICES_PATH
这是GPTUI基础服务组件的目录，在不修改源代码的情况下，不做更改。

### PLUGIN_PATH
这是GPTUI内置插件的路径，在不修改源代码的情况下，不做更改。

### DEFAULT_PLUGIN_PATH
这是GPTUI内置默认插件的路径，这些插件不在插件列表中显示，自动开启。在不修改源代码的情况下，不做更改。

### custom_plugin_path
这是GPTUI自定义插件的目录，可以修改。默认值为` ~/.gptui/plugins/`

### dot_env_path
此配置指定配置环境变量的文件的路径，在此指定的文件中配置API keys。默认值为`~/.gptui/.env_gptui`

### default_openai_parameters
该选项是一个字典，用于指定使用GPT聊天时的默认参数配置。

### default_conversation_parameters
该选项是一个字典，用于指定GPTUI默认的对话参数设置
-  `max_sent_tokens_raito`: float值，设置最大发送tokens的数量占整个模型tokens窗口的比例。例如，如果模型的tokens窗口大小为1000，该参数设置为0.6时，那么当要发送的聊天上下文tokens数超过600时，则会自动截断到600以下，剩下的400 tokens将作为模型回复tokens的窗口。因为模型的tokens窗口是发送tokens数量加接收tokens数量的总和，如果不做该设定，将有可能产生发送tokens占用太多上下文长度而导致模型无法回复或者模型回复内容不完整的情况。

### tui_config
此选项是一个字典，用于配置GPTUI的默认配置。
- `conversations_recover`: bool值，设置GPTUI的“Recovery”开关的默认值，是否自动保存和恢复GPTUI的状态。
- `voice_switch`: bool值，设置GPTUI的“Voice”开关的默认值，是否开启语音对话功能。
- `speak_switch`: bool值，设置GPTUI的“Speak”开关的默认值，是否开启朗读回复内容的功能。
- `file_wrap_display`: bool值，设置GPTUI的“Fold File”开关的默认值，是否开启自动折叠文件内容为文件图标的功能。
- `ai_care_switch`: bool值，设置GPTUI的“AI-Care”开关的默认值，是否开启AI-Care功能。
- `ai_care_depth`: int值，设置AI-Care在没有用户回应的情况下的最大主动说话次数。
- `ai_care_delay`: int值，以秒为单位，设置AI-Care的延迟启动时间。在一次对话完成后，AI-Care只有在此延迟时间之后才会起作用。
- `status_region_default`: str值，设置状态显示区域的默认显示内容。
- `waiting_receive_animation`: 特定的字符串类型，设置等待动画的类型，默认值为`“default”`。

### log_path
设置日志文件的路径。默认为`~/.gptui/logs.log`。

### workpath
设置GPTUI的工作路径。默认值为`~/.gptui/user`，默认向量数据库和临时文件等会存储在该目录下。

### directory_tree_path
GPTUI可显示的文件系统的根目录。默认值为`~/`。在导入导出文件时，GPTUI只能显示此目录下的文件和文件夹。

### conversation_path
设置导出和导入GPTUI对话记录时的文件路径。默认值为`~/.gptui/user/conversations`

### vector_memory_path
设置向量数据库的路径，默认值为`~/.gptui/user/vector_memory_database`

### terminal
设置所使用的终端，已测试的终端包括`termux`, `wezterm`。

### os
设置所使用的平台，提供四个选项：
- termux
- linux
- macos
- windows

由于termux并非一个完整的linux系统，所以把它作为一个单独的选项。

### default_plugins_used
此选项为一个列表，设置默认开启的插件，包括内置插件和自定义插件都可以在此处设置其默认开启状态。

### location_city
设置你的地理位置，让LLM可以获得你的位置信息，可以设置为你的城市名或者不设置。

### log_level
设置日志打印等级。

### openai_model_info
此选项是一个字典，存储各个模型的模型信息，模型的tokens_window在此设置。例如：
```
openai_model_info
  gpt-4-1106-preview:
    tokens_window: 128000
  gpt-4-0613:
    tokens_window: 8192
```
