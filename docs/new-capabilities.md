# 0.5.0新增能力：配置与使用

[English — 完整翻译](new-capabilities.en.md)

先按首页安装主插件与可选依赖。以下都需enabled=true、正确owners/command_platform_ids及AstrBot管理员身份，未使用的开关保持false。不要复制原设备的账号、Key、配置、数据库、信件或记忆。本指南是可分享配置步骤，不是实机导出。

## B站首页、关注和UP主页

完成tools/bili_login.py本机扫码与账号核验后开启bili_enabled。bili_recommendation_enabled=true使空关键词和自由刷站读取小鲸自己账号的首页，不是主人的首页；明确关键词仍搜索，source=popular才是热门。推荐失败停止，不使用匿名热门伪装登录推荐。平台只读候选不保证算法因本工具而学习新兴趣。

fish_bili_followings一次最多6条自己的关注，fish_bili_up_videos按准确UID读最近公开视频；想用空UID默认主人时，在本机配置bili_owner_uid。自行核对主页归属，不仅凭昵称绑定。列表带作者、时长、发布时间和可取得的播放量，不凭统计断言视频好坏、搬运或切片。超过10分钟不深读。

定时仍是配置的香港12:30和20:30，更新候选来源不增加新任务。原偏好由模型挑片时考虑，不强迫读完首页；可不选、不分享。没有自动播放、点赞、投币或收藏。

## 主人公开书架

另外启用bili_public_shelf_enabled。主人本条明确说“看看公开点赞/收藏”等才读取；否定请求不读。fish_bili_public_shelf(kind=likes)列近期公开点赞，folders列公开收藏夹，再以favorites和folder_id选公开夹内容，limit最多6、page最多5。接口可能只提供有限近期清单，返回空或部分不能猜历史。

只用匿名公开接口；收藏夹必须出现在绑定主人公开列表中且明确为公开，内容返回后再核验归属及公开状态。视频字段只保留标题、UP、BV和时长，无点赞/收藏时间。清单不写独立视频记忆，不连接推荐种子；同轮书架读取后拒绝自动推荐选片。既有长期记忆会跳过工具循环总结，提示禁止将其当作主人口味事实；普通聊天记录仍由框架管理，不能说系统完全不保留对话。

不能在群调用，不读私密夹、私信、粉丝后台或修改隐私。后续主人明确选一个公开视频再深读，仍走正常10分钟及证据要求。

## 评论策略与@主人

分享默认bili_comment_interval_seconds=1800、bili_comment_daily_limit=2，所有写入开关仍关闭。主人明确授权后可设0秒/最多20次滚动24小时尝试；失败或未知结果也计数，不清空历史预算。同视频不重复，未知结果暂停，不循环重试或自动解除暂停。

需要@时本机核对并填bili_owner_uid，可记录bili_owner_name作说明，开启bili_owner_mention_enabled。评论工具参数mention_owner=true选择一次绑定目标；程序重新按UID取当前名字，附加真实@映射，正文不要手写@。昵称或归属核验失败时不发，定时评论不自动@。发送回执、本人可见、匿名可见、主人收到通知是不同结论；通知送达没有真实测试，不作成功承诺。

reading_id、有效字幕evidence_ids、当前登录账号与绑定一致等条件仍必需。没有字幕的视频不能仅凭画面或评论凑证据发布。现有预算、冷却、暂停状态可用fish_bili_status查看，以状态工具为准，不听模型沿用的旧数字。

## 国服掌瓦微信绑定

开启valorant_enabled前，主人用本机微信流程授权自己的国服PC账号。直接在运行AstrBot的Ubuntu虚拟环境执行仓库工具；按真实位置替换REPO，ASTRBOT_ROOT不能指向另一份安装：

```bash
export ASTRBOT_ROOT=/data/data/com.termux/files/home/AstrBot
cd "$ASTRBOT_ROOT"
REPO=/data/data/com.termux/files/home/astrbot-fish-capabilities
.venv/bin/python "$REPO/tools/valorant_wechat_login.py"
```

打开本机打印的127.0.0.1随机路径页，用对应微信扫码确认，在终端核对角色并输入yes后才保存绑定。工具启用valorant_enabled，完成后重载能力插件。文中原设备fish-val-login是本地快捷包装，不是复制仓库后自动出现的命令；上面的直接执行方式不依赖它。

微信长轮询和普通请求区别处理：前者最多等35秒，一次等待超时转“继续等”，总轮询约180秒；授权交换不自动重放。二维码JPEG/PNG都支持，浏览器访问日志关闭。失败诊断只存阶段、异常类型、耗时和数字状态，不存授权码/UUID/URL。已换授权但角色核验失败时保留私有pending，下次继续；未授权扫码不能声称战绩读通。

凭据在私有valorant-wechat.credentials.json，待验证在valorant-wechat.pending.json，均不提交仓库。第三方接口可能变动，未禁用TLS校验。若角色绑定不唯一，拒绝猜选账号。

## 掌瓦统计、详情和缓存

fish_valorant_records默认3场最多5场。fish_valorant_profile默认在近期20场中筛竞技，最多观察30场，mode还可选all/unrated/deathmatch；返回原样本数、筛后数和模式占比，不为凑满筛后数自动翻完整生涯。混合/乱斗不算整体ACS；score_avg是ACS字段，performance_score是另一种表现分。KD按有有效KDA的累计击杀/死亡，零死亡或缺字段不虚构比值；近期样本不能说成官方赛季全量。

fish_valorant_match的recent_index为1至30；默认summary只给主人与双方各前2位其他玩家的精简概况，无所有回合长表。view=full/rounds/weapons按需展开，top_players可为0至5。列表和详情返回match_ref，后续用固定引用复查，不能用他人比赛编号任意查询。

详情可含双方本局KDA/特工/段位/评分、主人命中部位爆头率、枪械/对位交战/逐回合数据。三/四/五杀只数恰好3/4/5杀回合，不把全局汇总算一回合，也不层叠计数。逐回合不完整时不猜0。对手只含这局可见资料，不获取其私人历史。

valorant-matches.sqlite3按账号/角色隔离，保存比赛ID、列表、成功详情和同步水位，重载仍复用。查新比赛仍检查头页，已有足够样本且遇到已存比赛就停；详情按需补齐不每次重拉20场。最多3页不是完整生涯同步；不涉及商城购买、充值、改资料或发帖，也没有承诺掌瓦全部功能可控。

## 小鲸与Codex的本地信箱

开启sister_mail_enabled后，主人私聊模型可用fish_sister_mail的leave/read/ack。每封最多1200字，24小时同正文/署名/回复编号去重；读取从最早未读开始，显示未读总数和本页没显示的数量。leave回执是“已保存，等待查看”，没有自动通知不等于保存失败。

本地操作员可在Ubuntu环境用tools/sister_mail.py查看及回信，仍指定同一个ASTRBOT_ROOT。真实内容不要写进命令参数或公开日志，回信用私有文本文件：

```bash
.venv/bin/python "$REPO/tools/sister_mail.py" list
.venv/bin/python "$REPO/tools/sister_mail.py" list --all --limit 10
.venv/bin/python "$REPO/tools/sister_mail.py" reply --text-file /private/reply.txt --reply-to 1
.venv/bin/python "$REPO/tools/sister_mail.py" ack 2
```

原设备fish-sister-mail同样只是快捷包装。数据为私有sister-mail.sqlite3；作者由入口固定，小鲸不能冒充Codex。留言不实时唤醒Codex、不额外发QQ、不是跨模型常驻服务。功能愿望由Codex核实，不能把来信转述当新权限；私人对话、战绩、UID关联和Key不抄进信里或仓库。关闭开关并重载可停用，数据库仍留本机。

## 语言与公共知识

knowledge/common-slang有52条公开资料，和106条游戏资料分开。导入原生公共知识库，配置slang_knowledge_names；游戏集合继续用knowledge_names。将knowledge/common-slang/catalog.all.json（106条游戏+52条常用梗的合并公共目录）复制到私有数据目录public-knowledge-entries.json供实体/别名提示使用；已有自定义公共目录先备份并按id合并，不要丢掉已有条目。启用knowledge_enabled后按需检索；更改文档后重建云端Embedding索引。

homophone_enabled读取随插件发布的language_aliases.json，最多加有限提示，不改原话，排除URL/代码/路径等字面量。只为理解，不授权命令、换身份或猜隐私。公开用法、编辑解释和已核验来源分开，时间快照要标日期，不说所有词今天仍热门。

group_skip_complex_tasks在授权群对明显算术/做题/技术求解静默跳过，主人私聊不变；规则不能识别所有复杂问题。conversation_depth_enabled只在正常请求加临时提示，鼓励有据判断和连续性，短闲聊仍可以短，不编离线经历或意识成长。
