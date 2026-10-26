# 大肥鱼：AstrBot 能力扩展

[中文](README.md) | [English — 完整翻译](README.en.md)

在 AstrBot + NapCat 上增加意图接话、B站浏览与互动、天气、战绩、表情、长期记忆适配和统一时间表。支持以 ARM64 安卓平板作为主机，也提供电脑部署路线。分享版 **0.7.0 · 2026-10-26**。

这是需要配置的试用版，不是携带现成账号的整合包。所有能力开关默认关闭，主人身份和授权范围为空。仓库维护者署名不是机器人主人的身份配置，不分发任何人的私人聊天、记忆、提示词或登录态。

## 从这里开始

1. [从零部署：平板与电脑](docs/getting-started.md)，先跑通 QQ 文字回复，再逐项打开能力。
2. [让 DSH 或类似助手辅助部署](docs/assistant-deployment.md)，包含可复制的部署提示词和交付检查。
3. [0.7.0 新功能、配置与迁移](docs/release-0.7.0.md)，已有部署从这里看。
4. [隐私与身份配置](docs/privacy.md)、[验证范围](docs/validation.md)。

## 能力与边界

| 能力 | 行为与条件 |
| --- | --- |
| 统一时间表 | 主人私聊用自然语言调用 `fish_tasks` 创建、修改、暂停、恢复、取消任务；提醒、天气、商店、刷站和检查任务复用同一调度器 |
| 跨窗口时间线 | QQ 与 B站活动保存有限摘要，主人私聊可检索；历史事件不冒充当前状态，不自动向群公开 |
| 记忆检索与纠错 | `fish_memory_edit` 检索当前范围旧记忆，独立审查更正、版本校验、保留审计；依赖兼容 LivingMemory 接口 |
| B站阅读 | 搜索、本人账号首页推荐、候选选片、字幕和抽样画面、评论与札记；超过10分钟不深读，抽样不等于完整观看 |
| B站互动 | 独立开关与审核的评论、楼中楼、点赞收藏、表情和批准图库图片、关注动态、指定UP开播、每日最多一条碎碎念 |
| 主人B站@ | 核验发件人、接收账号和视频对象后阅读视频及评论，可决定回复；旧通知不回放，未知写入结果不重复发 |
| 群聊意图与静音 | 判断接话对象、合并积压，主人 `/闭嘴` 或意图决定停止后静音本群120秒；GCP桥接需核对补丁基线 |
| 日常能力 | 香港天气、私聊查授权群记录、有限嵌套转发、国服掌瓦微信战绩与每日商店、分类表情和公开知识库 |
| 语音识别 | 复用阿里云提供商Key，四种 Paraformer 路线、本地额度预留和短期缓存；不是 TTS，不自动发语音 |
| 上下文与语气 | 有限历史、滚动摘要、工具输出压缩、普通文字分段；追加陪伴表达约束，不覆盖原人格主体 |
| QQ恢复 | 独立 Termux 恢复器和看守，优先内置恢复、有限快速登录和可选密码回退；人工验证停止重试 |

不是所有参考机器定制都包含在本仓库：LivingMemory 双层群记忆尚未整理成完整可迁移补丁；GCP 补丁也不是任意上游版本的通用安装器。详见[记忆](docs/memory.md)与[意图桥接](docs/intent.md)。暗区突围PC战绩、Azure/Vocu调音和本地GPU语音不属于已完成功能。

## 目录和安装原则

主插件在 `astrbot_plugin_fish_capabilities/`，应复制到实际 AstrBot 的 `data/plugins/` 中。本仓库还含工具、恢复器和补丁，**不要把仓库根目录当单个 AstrBot 插件安装**。依赖要装进运行 AstrBot 的同一个 Python 环境。参考框架版本 AstrBot 4.29.1、NapCat 4.18.38，其他版本需检查适配。

`examples/config.disabled.json` 是全关模板，不是可直接运行的私人配置。B站、掌瓦、语音、公开写入分别启用，不会因打开总开关自动获得账号权限。

## 其他文档

[QQ恢复](docs/recovery.md) · [群聊控制](docs/group-controls.md) · [B站互动](docs/bili-social.md) · [已有能力配置](docs/new-capabilities.md) · [记忆时效](docs/memory-policy.md) · [表情](docs/memes.md)。旧版指南中的固定时间和旧限制以0.7.0迁移说明及本机实际配置为准。

## 测试与来源

```bash
python -m pip install -e '.[test]'
python -m pytest -q tests
python -m unittest discover -s recovery -p 'test_*.py'
```

隔离测试不能代替真实账号端到端验证。具体通过数量、设备检查与未实测事项见[验证记录](docs/validation.md)。HarmonyOS 后台存活和非官方QQ接入均不能保证永久稳定。

代码按 [AGPL-3.0](LICENSE) 发布，第三方来源及素材边界见 [NOTICE](NOTICE.md)。由 FigaroGao 发起、部署与维护；Codex（OpenAI）协助设计、实现、测试与文档。提交保留 Codex 共同作者署名，不代表 OpenAI 官方认证。
