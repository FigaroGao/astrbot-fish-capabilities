# 上游来源与发布范围

- AstrBot：https://github.com/AstrBotDevs/AstrBot 。通过插件 API 接入，内部指令管线适配针对参考版本检查。
- NapCat：https://github.com/NapNeko/NapCatQQ 。通过已有 OneBot 通信，不复制其协议实现。
- Group Chat Plus：https://github.com/Him666233/astrbot_plugin_group_chat_plus ，AGPL-3.0。仅发布最小接入补丁，保留上游归属。基线为已有定制版本，不能直接替代官方完整发行。
- LivingMemory：https://github.com/lxfight-s-Astrbot-Plugins/astrbot_plugin_livingmemory ，AGPL-3.0。本次只提供迁移边界说明，不包含完整记忆适配与用户记忆。
- 表情包参考：https://github.com/the-beating-light-of-the-nail/deepseek-chan-meme-pack 。不分发其图片，不替第三方资产重新授予授权。
- 天气：Open-Meteo（https://open-meteo.com/），其数据及服务条款分别适用。
- 研究时参考 chengzhi-c/astrbot_plugin_self_initiated_reply、kazamisama/astrbot_plugin_social_context；没有将其上游源码或测试复制到分享包。
- B站能力参考 https://github.com/c1overzz/dsh-bili-scroll 与 https://github.com/InariNGT-Ofiicial/dsh-bili-humanism 的职责分层；使用 bilibili-api-python 17.4.1 可选依赖。阅读和扫码已做参考设备检查，未测试真实公开评论；语音仍是关闭的DashScope原型。
- 公共无畏契约资料来源在knowledge/valorant/entries.json逐条列明，快照截至2026-10-24；不将原资料重新授权为项目原创。

不包含第三方源码缓存、SDK wheel、实机备份、日志、浏览器登录态、密钥、QQ 账号配置、聊天/记忆数据库或图库。源代码及本次补丁按 AGPL-3.0 发布，第三方服务和资源不受此许可证重新授权。

## English translation

AstrBot and NapCat use existing APIs; complete frameworks and QQ protocol implementations are excluded. Group Chat Plus is AGPL-3.0: only a minimal patch for a customized baseline is included. LivingMemory is AGPL-3.0: its complete customized memory adaptation and all user memories are excluded. Third-party meme images are excluded and retain separate rights. Weather uses Open-Meteo under separate service/data terms. Research referenced chengzhi-c/astrbot_plugin_self_initiated_reply and kazamisama/astrbot_plugin_social_context without copying their code or tests. Bilibili research referenced c1overzz/dsh-bili-scroll and InariNGT-Ofiicial/dsh-bili-humanism, using optional bilibili-api-python17.4.1. Reading and QR verification were checked, not real public comments. DashScope speech remains a disabled prototype. Public VALORANT sources are cited per entry in knowledge/valorant/entries.json as of2026-10-24; original source material is not relicensed as project-original content.

No upstream source caches, SDK wheels, device backups, logs, browser sessions, keys, account configurations, conversations/memory databases, or image libraries are included. Code and this patch use AGPL-3.0; third-party services and resources are not relicensed.


## 0.5.0新增来源 / Added sources in0.5.0

- 掌瓦微信登录流程参考 GuJi08233/astrbot_plugin_val_shop，实际许可证为AGPL-3.0，保留于astrbot_plugin_fish_capabilities/third_party/valorant-shop-LICENSE；战绩字段研究参考wuche-2453198/astrbot_plugin_valorant_analysis。没有复制第三方账号凭据、原始授权日志或关闭TLS验证的路径。Mainland VALORANT WeChat flow references GuJi08233/astrbot_plugin_val_shop under its actual AGPL-3.0 license,preserved in the listed file; field research also referenced wuche-2453198/astrbot_plugin_valorant_analysis. No third-party credentials,raw authorization logs,or certificate-bypass paths are included.
- B站@映射协议核对jackwener/opencli的clis/bilibili/comment.js；公开点赞接口核对DIYgod/RSSHub的lib/routes/bilibili/like.ts；只参考接口字段，未复制浏览器运行时或整体实现。Bilibili mention fields were checked against jackwener/opencli's clis/bilibili/comment.js and public likes against DIYgod/RSSHub's lib/routes/bilibili/like.ts; only protocol fields were referenced,without copying their browser runtimes or complete implementations.
- 新增52条公共梗与谐音资料逐条保留来源、核对日期与编辑解释标签；不是实时热榜。The52 added public slang/homophone entries retain per-entry sources,check dates,and editorial labels,and are not a live popularity chart.
- 本地信箱内容、账号UID绑定、掌瓦数据与缓存、公开书架查询结果、实机健康报告均不随发布。Local letters,UID bindings,VALORANT data/caches,shelf-query results,and device-health reports are excluded.

## 0.6.0新增范围 / Added scope in0.6.0

新增B站互动、通知、动态与表情面板使用可选bilibili-api-python17.4.1接口；图片仍只引用已核验公开图库，不随仓库分发。掌瓦每日商店沿用已注明AGPL来源的本人微信绑定流程，不复制第三方凭据。8条新增社区用语在knowledge/vct-bili-20261025/逐条保留来源与日期，编辑解释不等于首创或争议事实认证。群聊静音与转发展开通过现有AstrBot钩子及OneBot接口，不分发框架。审核上下文、待审草稿、订阅名单、互动回执、信件和数据库全部排除。

New Bilibili interactions, notifications, dynamics and emote-panel access use the optional bilibili-api-python17.4.1 interfaces. Images are references to the verified public library and are not distributed. The VALORANT shop reuses the owner's WeChat binding flow under the AGPL attribution already recorded, without third-party credentials. The eight additional community expressions retain per-entry sources and dates in knowledge/vct-bili-20261025; editorial explanations do not authenticate origins or disputed claims. Group silence and forward expansion use existing AstrBot hooks and OneBot APIs without distributing the framework. Review context, pending drafts, subscriptions, receipts, letters and databases are excluded.
