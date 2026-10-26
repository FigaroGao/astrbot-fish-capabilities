# 从零部署：平板或电脑

[English — 完整翻译](getting-started.en.md)

目标是先让自己的测试QQ正常文字聊天，再安装本仓库能力。不需要本地跑大模型；聊天、识图和Embedding可用云端API。本教程没有在每一种设备上重新安装验证。参考设备是ARM64安卓平板/HarmonyOS 4.2、Termux + Ubuntu proot，不能直接假定所有HarmonyOS版本兼容。

## 1. 准备与路线

准备测试QQ、稳定网络、足够存储及自己的聊天API。向量与识图是独立能力，普通文字聊天不必先买Embedding。Key只在本机管理页面输入。非官方QQ接入可能要求扫码、身份验证或限制账号。

| 主机 | 推荐路线 | 注意 |
| --- | --- | --- |
| 安卓ARM64平板 | Termux运行管理命令；AstrBot放Ubuntu proot，NapCat用官方Termux方案 | 原生Termux使用Bionic，桌面Linux wheel不一定兼容；在Ubuntu里安装Python依赖 |
| Windows电脑 | Python 3.12 + uv运行AstrBot源码；NapCat官方Windows包 | 关闭终端、电脑睡眠都会影响服务；Termux恢复器不能直接装Windows |
| Linux电脑 | Python 3.12 + uv源码运行；NapCat官方Linux安装器 | 按实际架构选择包，服务保活由宿主机管理 |

APK整合方案可自行研究，但其支持声明不等于本教程实测。本教程不同时安装多个整合包。为了简化网络，先不走Docker；Docker中的127.0.0.1不是宿主机或另一容器。

## 2A. 平板：Termux与AstrBot

从 [Termux官方安装说明](https://github.com/termux/termux-app#installation) 选择可信来源；插件应用保持同一签名来源。以下在**原生Termux**执行，逐条确认输出：

```bash
pkg update
pkg upgrade
pkg install git curl termux-tools proot-distro
termux-wake-lock
git clone https://github.com/fii6/astrbot_termux.git
cd astrbot_termux
```

先查看下载的脚本，再执行，不必重复运行已完成的安装：

```bash
bash ./astrbot_termux.sh
astr
```

该 [上游方案](https://github.com/fii6/astrbot_termux) 提供 `astr` 启动和 `astr shell` 进入AstrBot的Ubuntu环境。安装可能较慢；依赖失败时保留末尾错误，不要把Ubuntu命令贴到原生Termux反复尝试。确认实际AstrBot目录和Python环境，后面依赖都装在这里。若所用脚本版本改变路径，以实际输出为准。

## 2B. 电脑：AstrBot源码

安装Python 3.12、Git和 [uv](https://docs.astral.sh/uv/getting-started/installation/)。以下命令适用于PowerShell或Linux终端；在自己选的工作目录运行：

```bash
git clone --branch v4.29.1 https://github.com/AstrBotDevs/AstrBot.git
cd AstrBot
uv sync --python 3.12
uv run --no-sync main.py
```

固定版本用于复现本插件参考环境，不代表永远不升级；升级先备份检查兼容。官方源码路线见 [AstrBot部署说明](https://docs.astrbot.app/deploy/astrbot/cli.html)。后续装插件依赖后继续用 `--no-sync` 启动，避免同步环境移除额外依赖。

## 3. 启动NapCat与登录QQ

**平板原生Termux另开会话**，下载并检查 [官方Termux安装器](https://github.com/NapNeko/NapCat-Installer)：

```bash
cd ~
curl -fL -o napcat.termux.sh https://raw.githubusercontent.com/NapNeko/NapCat-Installer/main/script/install.termux.sh
bash napcat.termux.sh
proot-distro login napcat -- bash -c 'xvfb-run -a /root/Napcat/opt/QQ/qq --no-sandbox'
```

最后一行是该布局的启动命令，不要同时启动两份QQ。若安装器改变目录，先核对路径。用手机QQ扫终端二维码并完成官方验证。

**Windows**从 [NapCat官方发行页](https://github.com/NapNeko/NapCatQQ/releases) 下载官方Windows Shell一键包，按包内说明安装并运行 `napcat.bat`；不要使用平板的proot命令。**Linux电脑**按 [官方Shell指南](https://napneko.github.io/guide/boot/Shell) 下载检查安装器，选择本机CLI模式；不要误装Docker路线。

在主机浏览器打开 `http://127.0.0.1:6099/webui/`。登录密钥从本机启动日志取得，它不是QQ密码。手机上打开127.0.0.1访问的是手机自身，远程访问需要另设已认证隧道，不能直接公开6099。

## 4. 连接AstrBot、NapCat与聊天API

在同一主机浏览器打开 `http://127.0.0.1:6185`。初始登录信息以AstrBot启动日志为准，登录后设置自己的密码。添加QQ/aiocqhttp平台，填写自己取的ID，例如 `myqq`，启动OneBot v11反向WebSocket接收，监听127.0.0.1、端口6199。生成自己的访问Token。

在NapCat网络配置新增 **WebSocket客户端**，地址 `ws://127.0.0.1:6199/ws`，消息格式array，Token与AstrBot一致，启用并保存。不要将其误配成两个服务器。两个proot环境通常共享平板的网络命名空间，仍应实际验证连接日志；若用Docker或虚拟机需重新设计地址。

AstrBot模型提供商里配置自己的聊天API、实际可用模型ID，选择其为当前会话模型。DeepSeek只做文字时不应假定它能识图；图片需另配真实支持视觉的提供商。把自己QQ号加入AstrBot管理员。

先私聊测试QQ发送一句普通话，确认NapCat收到、WebSocket连接、AstrBot调用成功且QQ收到回复。群聊先用测试群@机器人，检查唤醒设置；不要此时就打开自动刷站和公开评论。

## 5. 安装本仓库主插件

下载仓库后只复制 `astrbot_plugin_fish_capabilities` 文件夹到实际AstrBot的 `data/plugins/`。插件路径应类似 `AstrBot/data/plugins/astrbot_plugin_fish_capabilities/main.py`，不要多套一层仓库目录。

电脑源码路线可在AstrBot目录旁克隆仓库。Windows PowerShell示例（在AstrBot目录内）：

```powershell
git clone https://github.com/FigaroGao/astrbot-fish-capabilities.git ../fish-capabilities
Copy-Item -Recurse ../fish-capabilities/astrbot_plugin_fish_capabilities ./data/plugins/
uv pip install --python .venv/Scripts/python.exe -e '../fish-capabilities[bilibili,speech]'
```

Linux或**平板 `astr shell` 进入Ubuntu后**，先切到实际AstrBot目录，确认其中有 `.venv/bin/python`，再执行：

```bash
git clone https://github.com/FigaroGao/astrbot-fish-capabilities.git ../fish-capabilities
cp -r ../fish-capabilities/astrbot_plugin_fish_capabilities data/plugins/
uv pip install --python .venv/bin/python -e '../fish-capabilities[bilibili,speech]'
```

若Ubuntu中无uv，使用该Python自身的pip安装同一依赖；不能改用原生Termux的pip。`speech`为语音识别可选依赖，`bilibili`为刷站可选依赖，不用时可省略。FFmpeg在运行AstrBot的Ubuntu里通过 `apt update`、`apt install ffmpeg` 安装；Windows需自行将FFmpeg加入PATH。重载插件或重启AstrBot，不要为此重启已经在线的NapCat。

## 6. 逐项配置与验证

在插件配置中先只填自己的 `owners`、`command_platform_ids`，将主人加入核心管理员。UMO是框架的完整会话标识，不只一个群号；从本机真实事件/配置确认。开启 `enabled` 与 `weather_enabled`，在主人私聊问香港天气。确认工具成功后再启用下面功能。

| 想启用 | 还需要 |
| --- | --- |
| 私聊查群 | `history_enabled`、自己的 `history_group_sessions`；先积累本地记录，不保证完整历史 |
| 表情 | 导入有权使用的图片并批准索引ID；参见[表情指南](memes.md) |
| B站 | 同一Python环境的SDK、独立账号扫码、正确绑定；参见[互动指南](bili-social.md)；写入和审核分别开启 |
| 掌瓦商店 | `valorant_enabled`，本机微信授权自己的国服账号；工具的 `ASTRBOT_ROOT` 指向实际AstrBot，不照抄平板默认路径 |
| 云端记忆 | 配好自己的Embedding提供商和兼容LivingMemory；不导入别人的库，不随意改变既有向量维度 |
| 统一时间表、时间线、记忆纠错、ASR | 按[0.7.0说明](release-0.7.0.md)逐项开启；并非启用插件就全部生效 |
| 群聊读空气 | 对照[意图桥接](intent.md)，补丁不匹配就停止；普通文字聊天不依赖这个补丁 |

插件工具需要被当前模型实际允许使用，模型自称“能用”不能代替工具回执。先只读后写入、先私人测试后群聊。公开评论/动态和账号操作使用专门小号，并由自己的配置明确授权。

## 7. 保活、恢复和日常启动

HarmonyOS为Termux允许后台活动、自启动及不受电池优化限制，最近任务中锁定；唤醒锁只解决部分休眠，不保证系统不清理。浏览器只是WebUI，关闭浏览器本身不应停止后台服务。使用tmux或服务托管保留终端进程，确认宿主环境正确后再设置开机启动。

平板重启后先在原生Termux运行 `termux-wake-lock`，用已有管理方式启动AstrBot及NapCat；不要重复安装。若没有其他NapCat管理器，可使用第3节启动命令；已经有恢复器/服务时先看其状态，不另启第二份QQ。QQ登录凭据失效仍可能需要手机验证。

需要无人值守恢复时读[恢复方案](recovery.md)，先修改实际路径并备份。该安装器面向Termux/runit，不是Windows通用服务安装器。电脑先用操作系统的服务管理保活，关闭睡眠影响需要自行选择；不要把“自动重启进程”等同于“绕过QQ验证”。

## 8. 验收与排错

| 现象 | 优先检查 |
| --- | --- |
| 登录WebUI但QQ不回复 | QQ在线、反向WS、Token、AstrBot平台启用、模型API和唤醒条件；三个WebUI可开不代表消息链路已通 |
| 安装依赖报架构/编译错 | 是否误在原生Termux安装Linux wheel，是否Python3.12/ARM64兼容；保留实际异常 |
| 工具不可用 | 总开关、各项开关、主人+管理员、平台ID、会话范围、模型工具权限与插件加载日志 |
| 任务没有执行 | 列表真实任务ID、香港时间、开关、执行回执；错过时间不会批量补发 |
| 记忆认错主人 | 不照抄别人提示词和数据库；按[隐私检查](privacy.md)查来源与scope |
| 手机扫了仍verify失败 | 用本机登录工具继续已有待核验流程，检查账号归属；不公开Cookie、不反复开并行扫码 |

完成文字、天气、授权群范围、锁屏一段时间、网络恢复等测试并记录实际结果。没有实际运行的项目标为未验证；公开写入测试须由部署者自己明确安排。备份保存在仓库外，WebUI不暴露公网。

## 9. 可选：私有冷档与信箱连接

文字聊天稳定后再按[0.7.1指南](cold-memory.md)开启冷档、回忆和夜间日记。电脑ADB心跳配置留在仓库外；夜间任务初始香港05:00，已有时间表需修改原任务，不重复创建。没有心跳或近期聊天会跳过，不代表故障。它不自动唤醒Codex。
