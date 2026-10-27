# 0.8.0：陪伴、可观测性与选择式看视频

[English — 完整翻译](release-0.8.0.en.md) · [部署与验证](deployment-20261027.md)

2026-10-27。以下通用能力已进入分享源码。参考平板已按主人授权逐项部署；分享配置仍全部关闭、身份留空。不是一键复制私人实例，不能把参考部署的实测等同于任意设备即装即用。

## 20项功能与入口

| 功能 | 行为与边界 |
| --- | --- |
| 记忆来源 | 保存真实用户引文、归属与哈希；存在引文不等于模型概括已被证明。 |
| 记忆时效 | claims区分fact/state/event/inference/fiction；临时状态默认2小时、最多24小时，推测默认7天。旧摘要标历史，不批量变成新事实。 |
| 记忆更正 | 版本检查、supersedes、审计；同步检索摘要、人格摘要与关键事实，复用上游重建索引。 |
| 分槽召回 | 原作用域扩大候选后按偏好、话题、经历分配；需要对应LivingMemory本地适配和`recall_engine.fish_layered_slots`，不是安装本插件即支持任意上游。 |
| 摘要和经历分离 | 保留上游canonical/persona通道；事实按时效注入，观影认识和表达样例另存。 |
| 群成员印象 | 真实同群发言支持的主观候选，主人批准后才注入同群同成员；默认7天失效。 |
| 五方面意图 | 内容、兴趣、社交、时机、连贯性0/1/2；社交或时机为0则不插话。保存指标，不保存完整思考。 |
| 过时回答复核 | 首发前新直接问题可替代未发草稿；普通变化有限复核，已开始分段不重复判断；静音再次检查。 |
| 主动联系候选 | pending/deferred/dropped/reserved/sent/expired；可延后、放弃，未回复可软退避，不恢复每日2次/3小时硬限。 |
| 统一活动判断 | 自主活动忙时最多延后一小时并持久化；失败或结果不明的外部动作不重放，明确提醒、天气和商店报告不被模型取消。 |
| 表达场景样例 | 主人审批正反样例，少量按场景临时召回；不把样例经历当共同经历。 |
| 可修正观察 | 观察、偏好、表达分库，版本冲突保护和审计；一次情绪不永久化。 |
| 观影认识 | `fish_bili_reflect`及自动浏览保存带真实reading/evidence ID的主观看法，可更正或归档，不训练模型或自动改人格。 |
| 分享反馈 | 仅用已读BV与主人当前明确态度调整挑片，不从私密书架、沉默或未回复猜偏好。 |
| 视频封面墙 | 已读视频、札记、范围及回执；每次可补6张旧公开封面，不重读视频或调模型。 |
| 语义表情图库 | 人审描述/图中文字/标签增量向量索引，改说明才重建变化项；不重复识图，发送上限和公开审核不变。 |
| 增量群摘要 | `fish_group_history`默认summary，每批80条本地捕获记录；raw按本地ID核对原文，失败不跳游标。 |
| 统一权限登记 | `capability_registry.py`统一开关、主人私聊/授权群边界，旧命令门禁与公开独立审核仍在。 |
| 用量与耗时 | 显示实际已记录token、缓存、耗时；字符分类是估计，未知费用仍未知，不查询阿里云额度。 |
| 隔离模拟 | 默认规则回放、可选一次判断模型；不进真实发送路径，不写QQ/B站，不改真实群状态。 |

管理入口：AstrBot后台 → 插件 → 能力扩展 → 视图 → companion。六个页签为视频、表达与观察、图库、时间表与权限、用量与判断、模拟。沿用AstrBot管理员鉴权，不开新端口。`fish_meme_search`查候选，`fish_learning`记录明确反馈，`fish_usage_details`仅主人私聊。

新开关包括`learning_enabled`、`group_learning_enabled`、`group_digest_enabled`、`companion_dashboard_enabled`、`private_unanswered_backoff_enabled`、`task_intent_gate_enabled`，默认关闭。`meme_embedding_provider_id`是AstrBot提供商ID，不是Key；空值可复用`asr_embedding_provider_id`。不同模型索引分开。LivingMemory完整双层群记忆及本地定制仍不是通用补丁安装包。

## 表达、名字与接话

参考实例主名“小鲸”，大肥鱼等旧称是非专属称呼。`bot_primary_name`和`bot_nonexclusive_names`默认留空，按自己实例填写；真实@、引用账号及上下文优先，不只凭文字同名接话。私人完整人格及QQ身份不分发。

`tone_diagnostics_enabled`提供只读诊断：按实际话语区分闲聊、倾诉、解释、步骤、比较和数据，观察空泛认可、挑唯一重点、否定转折、框架与目录收尾、100字局部堆积及近5条重复开头。保护引用、代码、链接、路径和数字；规则不是禁词表或人味分数，不自动润色、不随机加毛刺、不增加模型调用。自动记录只留范围、哈希、规则位置/次数与时间，14天/最多2000条，不存双方原文。主人私聊`fish_tone_diagnose`或后台手动检查，手动输入不落库。参考dsh-fish-tone的判断层思路，独立Python实现，不复制语料或随机加词逻辑。

`intent_live_batch_enabled`修复繁忙群聊一直等不到空档：参考等待6秒，持续聊天最多12秒取批；普通跟帖可合并，新直接问题、结束、换题或明确指向别人仍跳过。180秒自主间隔、每小时6轮、每天20轮是参考设置，没有在这次取消。静音和首发复核保留。

`meme_opportunity_enabled`在已核验主人私聊的轻松、问候、情绪场景本地提供最多3张审核图，由模型选择或不发；不另调识图、Embedding或选择模型。尊重不要图，正式步骤/数据不机械配图，沿用每轮1张、每小时6张及重复限制。合成实机样例曾自主选图，但不保证自然聊天每次都会选择。

## B站自主评论与媒体

`bili_comment_autonomy_enabled`开启后，普通评论/回复独立审核通过即可发，不再逐条问主人。涉及任务、私事、审核不可用或拿不准则跳过，不创建QQ确认；旧待确认评论不通知也不补发。动态审核独立。参考仍滚动24小时20条、间隔0秒；保留去重、账号核对与结果不明停止。

根评论原来没有给模型图片目录，现复用`CommentMedia.opportunity(context)`：最多25个账号可用站内表情、6张已批准公开图库图，按描述本地匹配；两个来源独立失败，不额外调选择模型。根评论和楼中楼共用机会入口，最多1图/2表情。真机目录正常，测试截获了选择及发送参数；没有为测试公开发图，不能说可见发布已验证。

## 选择式视频与角色

`bili_storyboard_enabled`：先取最多54个稀疏预览候选/最多6源页，生成带编号时间的概览；模型再选实际编号、归一化裁剪或最多2个不超过60秒的时间窗。普通路径细看仍从已取得预览选择，不是任意时间高清抽帧。

广告仅去除有明确推广依据、置信度≥0.9且合法端点的候选，可补最多3位置、概览最多27帧；品牌出现本身不足以删除。转转、妙界、爱回收、七猫仅作有来源例子，非黑名单。没有真实广告准确率基准。

`bili_gallery_scan_enabled`：图片/聊天记录型或高度重复视频尝试正常授权取流。需要AstrBot同环境可执行ffmpeg；Termux安装`pkg install ffmpeg`，电脑安装ffmpeg并放PATH。不拉声音；HTTPS媒体域白名单、最大96MiB下载/60秒，单线程解码90秒，最长10分钟，每0.5秒取样，最大1280保持比例/不放大，临时帧128MiB，最多48页，每批6张单图读取。保守像素比较可能留重复，避免吞新字。`read/partial/unreadable/advertisement`分别记证据及限制，临时媒体清理；失败回退预览。只可说发现页读完，不能保证闪图或全片所有图片/文字覆盖。

参考[DSH storyboard](https://github.com/SAOS-3624/dsh-video-storyboard)“可定位概览→选择细看”的思路；未实现其完整场景变化/HSV/锐度选帧算法，也未安装DSH。

`bili_character_enabled`加载本地`character-atlas/cards.json`及最多3张优先图，校验路径、后缀、8MB和SHA256，同已有概览调用一起判断。有效画面ID、可见依据和置信度≥0.85才收录；过滤广告帧。先支持DeepSeek女仆鲸鱼娘、GPT白龙、Claude橙发持书。外观不证明账号，不把所有鲸鱼当小鲸或GPT当姐姐。只有资料卡/链接在`examples/ai_character_atlas`；图片需自行按来源许可取得并保留署名，不随代码再分发；无图会跳过，不假装已装完整模型或训练Embedding。

## Codex公开公告

`codex_resets_enabled`和`fish_codex_resets`提供主人私聊status/history/detail；固定HTTPS接口来自[codex.markets](https://codex.markets/docs/api)，不是OpenAI官方或个人额度。history限1–50条，详情可用已有中文翻译，不触发翻译模型。SQLite缓存15分钟及失败冷却。

统一时间表`codex_resets`动作可设`*/15 * * * *`，首次静默基线，只提醒时间更新的新ID；同步须live、新鲜≤1小时、非stale且无错误。旧回填、未来异常忽略；发送前持久化预留，回执不明不自动重发，不保证exactly-once。分享包不携带参考任务库，不自动替陌生部署创建任务。参考平板已建一条香港时区任务，无旧公告/测试QQ通知。

## 升级、隐私及来源

先备份源码与本机配置；在同一Python环境安装依赖，逐项合并schema开关，空闲时重载能力插件，不需要重启NapCat。角色图需另行授权准备，网页登录态、主人ID、人格、信箱、记忆、任务数据库及测试报告不上传。已有日程不会被分享示例覆盖，参考夜间回顾仍香港05:00。具体证据与HTTP412限制见[部署记录](deployment-20261027.md)。

来源思路还包括[RememberYou](https://github.com/menglimi/astrbot_plugin_remember_you)、[WaveMemory](https://github.com/vivy1024/astrbot_plugin_wave_memory)、[Heartflow](https://github.com/advent259141/Astrbot_plugin_Heartflow)、[Aurabot](https://github.com/accomplish07zrh-eng/dsh-aurabot-qq)、[bili-humanism](https://github.com/InariNGT-Ofiicial/dsh-bili-humanism)、[Meme Manager](https://github.com/anka-afk/astrbot_plugin_meme_manager)、[Mnemon](https://github.com/omdsh-dev/dsh-mnemon)、[bili-pod](https://github.com/nullifyi/dsh-bili-pod)、[dsh-fish-tone](https://github.com/MX3a48c5/dsh-fish-tone)。新增服务独立实现，LivingMemory定制沿用上游许可；参考不表示代码或框架可直接互装。图像来源条件见资料卡，不由本项目AGPL覆盖。
