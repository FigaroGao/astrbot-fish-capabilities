# Illustrated usage examples

[中文](examples.md) | [English](examples.en.md)

These are explanatory diagrams, not screenshots of live conversations or end-to-end test receipts. No real account, private chat, key or game record is included.

## 1. Browsing yields when the owner starts chatting

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

Reading and chat do not compete as independent senders. Read material is retained; she may choose another topic later or stay quiet.

## 2. Mentioning her on Bilibili: read, then decide

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

Only verified owner mentions trigger this flow. Submission does not establish public visibility, notification delivery or reading; uncertain writes are not automatically repeated.

## 3. Reusing the schedule: weather and the VALORANT shop

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

This illustrates task composition, not a task created for repository visitors. VALORANT requires their own binding; natural-language requests still map to registered actions and local configuration.

## 4. Group pause: two minutes in this group

```mermaid
stateDiagram-v2
 [*] --> Listening
 Listening --> Quiet: 主人闭嘴命令或意图停止 / Owner command or intent pause
 Quiet --> Quiet: 阻止本群排队文字 / Suppress queued group text
 Quiet --> Listening: 两分钟后新消息或主人恢复 / New messages after two minutes or owner resume
```

This is group silence, not global shutdown. Previously queued material is not automatically replayed when the timer expires.

[Choose and install capabilities](capabilities.en.md) · [Overall architecture](architecture.en.md)
