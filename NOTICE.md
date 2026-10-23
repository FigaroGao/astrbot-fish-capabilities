# 上游来源与发布范围

- AstrBot：https://github.com/AstrBotDevs/AstrBot 。通过插件 API 接入，内部指令管线适配针对参考版本检查。
- NapCat：https://github.com/NapNeko/NapCatQQ 。通过已有 OneBot 通信，不复制其协议实现。
- Group Chat Plus：https://github.com/Him666233/astrbot_plugin_group_chat_plus ，AGPL-3.0。仅发布最小接入补丁，保留上游归属。基线为已有定制版本，不能直接替代官方完整发行。
- LivingMemory：https://github.com/lxfight-s-Astrbot-Plugins/astrbot_plugin_livingmemory ，AGPL-3.0。本次只提供迁移边界说明，不包含完整记忆适配与用户记忆。
- 表情包参考：https://github.com/the-beating-light-of-the-nail/deepseek-chan-meme-pack 。不分发其图片，不替第三方资产重新授予授权。
- 天气：Open-Meteo（https://open-meteo.com/），其数据及服务条款分别适用。
- 研究时参考 chengzhi-c/astrbot_plugin_self_initiated_reply、kazamisama/astrbot_plugin_social_context；没有将其上游源码或测试复制到分享包。
- 保留但默认关闭的 B站原型参考 c1overzz/dsh-bili-scroll 与 InariNGT-Ofiicial/dsh-bili-humanism 的职责分层，使用 bilibili-api-python 可选依赖；语音原型使用 DashScope。两者未完成实机验收。

不包含第三方源码缓存、SDK wheel、实机备份、日志、浏览器登录态、密钥、QQ 账号配置、聊天/记忆数据库或图库。源代码及本次补丁按 AGPL-3.0 发布，第三方服务和资源不受此许可证重新授权。
