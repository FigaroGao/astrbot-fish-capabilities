# 功能分类与安装入口

[中文](capabilities.md) | [English](capabilities.en.md)

fish-val、fish-bili等是功能导航名，不是独立插件包。多数能力共用 astrbot_plugin_fish_capabilities 和主脑；只需下载一次通用源码、安装主插件，再选择开启所需功能。恢复器与Screenmate走各自安装路线。

[下载通用源码ZIP](https://github.com/FigaroGao/astrbot-fish-capabilities/archive/refs/heads/main.zip) · [从零安装](getting-started.md) · [主脑图](architecture.md)

| 入口 | 分类 | 主要功能 | 配置指南 | 源码 |
|---|---|---|---|---|
| [fish-brain](#fish-brain) | 共享主脑 | 注意力、工作状态、抢占、人格上下文 | [指南](brain-core.md) | [源码](../astrbot_plugin_fish_capabilities/services/brain.py) |
| [fish-chat](#fish-chat) | 聊天与接话 | 群聊意图、静音、积压合并与分段 | [指南](intent.md) | [源码](../astrbot_plugin_fish_capabilities/services/intent_runtime.py) |
| [fish-memory](#fish-memory) | 记忆与时间线 | 长期记忆适配、冷档、纠错、活动索引 | [指南](memory.md) | [源码](../astrbot_plugin_fish_capabilities/services/memory_editor.py) |
| [fish-bili](#fish-bili) | B站 | 选片、视频理解、话题、评论与动态 | [指南](bili-social.md) | [源码](../astrbot_plugin_fish_capabilities/services/bilibili.py) |
| [fish-val](#fish-val) | 掌瓦 | 微信绑定、战绩、增量记录与每日商店 | [指南](new-capabilities.md) | [源码](../astrbot_plugin_fish_capabilities/services/valorant.py) |
| [fish-canvas](#fish-canvas) | 课程与Canvas | CityU课程、作业、公告与个人进度 | [指南](update-20261029.md) | [源码](../astrbot_plugin_fish_capabilities/services/course_context.py) |
| [fish-tasks](#fish-tasks) | 统一时间表 | 自然语言提醒、定时刷站与维护任务 | [指南](release-0.7.0.md) | [源码](../astrbot_plugin_fish_capabilities/services/timetable.py) |
| [fish-meme](#fish-meme) | 表情与语气 | 分类图库、发送机会、表达参考与诊断 | [指南](memes.md) | [源码](../astrbot_plugin_fish_capabilities/services/tone_diagnostics.py) |
| [fish-weather](#fish-weather) | 天气等日常工具 | 香港天气、授权群记录等确定性查询 | [指南](getting-started.md) | [源码](../astrbot_plugin_fish_capabilities/services/weather.py) |
| [fish-speech](#fish-speech) | 语音 | 语音识别与可选TTS适配 | [指南](update-20261031.md) | [源码](../astrbot_plugin_fish_capabilities/services/asr.py) |
| [fish-mail](#fish-mail) | 信箱 | 本地留言、回信、已读与连接状态 | [指南](cold-memory.md) | [源码](../astrbot_plugin_fish_capabilities/services/sister_mail.py) |
| [fish-recovery](#fish-recovery) | QQ恢复 | 独立恢复器、有限重登与人工验证停止 | [指南](recovery.md) | [源码](../recovery/) |

<a id="fish-brain"></a>

## fish-brain · 共享主脑

注意力、工作状态、抢占、人格上下文。

[下载来源](https://github.com/FigaroGao/astrbot-fish-capabilities/archive/refs/heads/main.zip) → [主插件](../astrbot_plugin_fish_capabilities/) → [配置与使用](brain-core.md)

<a id="fish-chat"></a>

## fish-chat · 聊天与接话

群聊意图、静音、积压合并与分段。

[下载来源](https://github.com/FigaroGao/astrbot-fish-capabilities/archive/refs/heads/main.zip) → [主插件](../astrbot_plugin_fish_capabilities/) → [配置与使用](intent.md)

<a id="fish-memory"></a>

## fish-memory · 记忆与时间线

长期记忆适配、冷档、纠错、活动索引。

[下载来源](https://github.com/FigaroGao/astrbot-fish-capabilities/archive/refs/heads/main.zip) → [主插件](../astrbot_plugin_fish_capabilities/) → [配置与使用](memory.md)

<a id="fish-bili"></a>

## fish-bili · B站

选片、视频理解、话题、评论与动态。

[下载来源](https://github.com/FigaroGao/astrbot-fish-capabilities/archive/refs/heads/main.zip) → [主插件](../astrbot_plugin_fish_capabilities/) → [配置与使用](bili-social.md)

[本机工具](../tools/bili_login.py)须按指南在对应环境运行，并先设置实际 ASTRBOT_ROOT。fish-val-login等是原设备快捷包装，克隆仓库不会自动创建它们。

<a id="fish-val"></a>

## fish-val · 掌瓦

微信绑定、战绩、增量记录与每日商店。

[下载来源](https://github.com/FigaroGao/astrbot-fish-capabilities/archive/refs/heads/main.zip) → [主插件](../astrbot_plugin_fish_capabilities/) → [配置与使用](new-capabilities.md)

[本机工具](../tools/valorant_wechat_login.py)须按指南在对应环境运行，并先设置实际 ASTRBOT_ROOT。fish-val-login等是原设备快捷包装，克隆仓库不会自动创建它们。

<a id="fish-canvas"></a>

## fish-canvas · 课程与Canvas

CityU课程、作业、公告与个人进度。

[下载来源](https://github.com/FigaroGao/astrbot-fish-capabilities/archive/refs/heads/main.zip) → [主插件](../astrbot_plugin_fish_capabilities/) → [配置与使用](update-20261029.md)

[本机工具](../tools/canvas_login.py)须按指南在对应环境运行，并先设置实际 ASTRBOT_ROOT。fish-val-login等是原设备快捷包装，克隆仓库不会自动创建它们。

<a id="fish-tasks"></a>

## fish-tasks · 统一时间表

自然语言提醒、定时刷站与维护任务。

[下载来源](https://github.com/FigaroGao/astrbot-fish-capabilities/archive/refs/heads/main.zip) → [主插件](../astrbot_plugin_fish_capabilities/) → [配置与使用](release-0.7.0.md)

<a id="fish-meme"></a>

## fish-meme · 表情与语气

分类图库、发送机会、表达参考与诊断。

[下载来源](https://github.com/FigaroGao/astrbot-fish-capabilities/archive/refs/heads/main.zip) → [主插件](../astrbot_plugin_fish_capabilities/) → [配置与使用](memes.md)

<a id="fish-weather"></a>

## fish-weather · 天气等日常工具

香港天气、授权群记录等确定性查询。

[下载来源](https://github.com/FigaroGao/astrbot-fish-capabilities/archive/refs/heads/main.zip) → [主插件](../astrbot_plugin_fish_capabilities/) → [配置与使用](getting-started.md)

<a id="fish-speech"></a>

## fish-speech · 语音

语音识别与可选TTS适配。

[下载来源](https://github.com/FigaroGao/astrbot-fish-capabilities/archive/refs/heads/main.zip) → [主插件](../astrbot_plugin_fish_capabilities/) → [配置与使用](update-20261031.md)

<a id="fish-mail"></a>

## fish-mail · 信箱

本地留言、回信、已读与连接状态。

[下载来源](https://github.com/FigaroGao/astrbot-fish-capabilities/archive/refs/heads/main.zip) → [主插件](../astrbot_plugin_fish_capabilities/) → [配置与使用](cold-memory.md)

[本机工具](../tools/sister_mail.py)须按指南在对应环境运行，并先设置实际 ASTRBOT_ROOT。fish-val-login等是原设备快捷包装，克隆仓库不会自动创建它们。

<a id="fish-recovery"></a>

## fish-recovery · QQ恢复

独立恢复器、有限重登与人工验证停止。

下载同一源码包中的[恢复器](../recovery/)与[看守插件](../astrbot_plugin_fish_host_guard/)，按恢复指南单独安装；不是装好主插件就自动启用。

## 桌面陪伴

[下载与配置：Xiaojing-Screenmate](https://github.com/FigaroGao/Xiaojing-Screenmate)。独立电脑端组件，不包含在能力插件中。
