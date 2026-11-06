# 使用示例图

[中文](examples.md) | [English](examples.en.md)

以下是机制示意图，不是真实聊天截图或端到端实测回执。不包含真实账号、私聊、密钥或战绩。

## 1. 主人找她时，刷站让路

```mermaid
sequenceDiagram
 actor Owner as 主人 / Owner
 participant QQ
 participant Brain as Brain Core
 participant Bili as B站执行器 / Reader
 Bili->>Brain: 已完成一条阅读 / One reading saved
 Owner->>QQ: 发来新消息 / New message
 QQ->>Brain: 更新交互状态 / Update interaction state
 Brain-->>Bili: 下一条读取前让路 / Yield before next read
 QQ-->>Owner: 原生聊天回复 / Native chat response
 Note over Brain,Bili: 已读资料保留为记忆与话题；不保证中断后自动续播同一条 / Read material is retained, resuming the same video is not guaranteed
```

不是看视频和聊天各自争着发消息。已读内容保留；她之后可以再选话题，也可以安静。

## 2. B站@她：先读，再决定回不回

```mermaid
flowchart TD
 A["主人在视频评论区@ / Owner mentions account"] --> B["核对通知账号、主人UID和视频 / Verify notice, owner and video"]
 B --> C["读取可用字幕、画面与评论 / Read available subtitles, frames and comments"]
 C --> D["结合主人原评论生成候选 / Draft in context of the owner comment"]
 D --> E{"权限、内容审核、预算、去重 / Permission, review, budget, dedup"}
 E -->|"通过 / Pass"| F["尝试回复原评论 / Attempt reply to original comment"]
 E -->|"不通过或不确定 / Reject or uncertain"| G["不发布；按原审核机制处理 / No publication; existing review flow"]
 F --> H["保存提交或不确定回执 / Record submitted or uncertain outcome"]
```

只有经过核验的主人提及会触发这条流程。提交不等于公开可见、通知送达或已读；不确定时不自动补发。

## 3. 复用日程：天气和掌瓦商店

```mermaid
flowchart TD
 A["主人：每天10:30查天气和商店 / Owner: check weather and shop at 10:30"] --> B["现有Agent调用fish_tasks / Native agent calls fish_tasks"]
 B --> C["确认已注册动作和任务参数 / Validate registered actions and arguments"]
 C --> D["统一时间表保存任务 / Timetable stores task"]
 D --> E["到时执行已有工具 / Existing tools run when due"]
 E --> F["天气服务 / Weather service"]
 E --> G["已绑定掌瓦 / Bound VALORANT service"]
 F --> H["按真实结果回复；失败不编造 / Report actual results, not invented success"]
 G --> H
```

这是任务组合示意，不是已为访问仓库的人创建了任务。掌瓦要先完成自己的绑定；自然语言请求仍需按现有任务动作和配置落地。

## 4. 群聊暂停：本群两分钟

```mermaid
stateDiagram-v2
 [*] --> Listening
 Listening --> Quiet: 主人闭嘴命令或意图停止 / Owner command or intent pause
 Quiet --> Quiet: 阻止本群排队文字 / Suppress queued group text
 Quiet --> Listening: 两分钟后新消息或主人恢复 / New messages after two minutes or owner resume
```

这张图描述群静音，不是全局停机。既有排队内容不会仅因时间到期就自动补发。

[按功能选择与安装](capabilities.md) · [主脑总图](architecture.md)
