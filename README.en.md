# Fish: AstrBot Capability Extensions

[中文](README.md) | [English — full translation](README.en.md)

Extend AstrBot on an idle ARM64 tablet into a QQ bot that understands who a group message addresses, retrieves information on demand, browses Bilibili, initiates private conversations, and controls context costs. The project reuses Termux, Ubuntu proot, NapCat, and AstrBot rather than implementing the QQ protocol. Updated: 2026-10-25; sharing release 0.5.0.

This experimental distribution requires configuration and adaptation. Every capability switch defaults to off. It does not reproduce the original device's accounts, conversations, memories, image library, or login sessions. This English version is a complete section-by-section translation of the Chinese version, with the same configuration, limits, and validation conclusions.

## Additions and fixes in this release

This release collects work completed since public version0.4.0. Deployment observations and interface checks mostly date to2026-10-24; the release was prepared on2026-10-25. Experimental prototypes are not all presented as deployed features.

| Module | Changes in0.5.0 |
| --- | --- |
| Bilibili selection | The signed-in account homepage is an optional default source; keyword search, popular videos, followings, and UP uploads remain distinct; popular results never masquerade as personalized recommendations |
| Public shelf | On an explicit owner request, anonymously reads the bound owner's public likes/favorites, at most6 entries; rejects private folders and does not use the shelf as a recommendation seed |
| Comments | A single mention bound to the owner's UID; separate submitted, author-visible, and anonymously visible states; configurable spacing and a rolling24-hour ceiling up to20, without duplicate posts or resends |
| Previews | Preserves source-preview pixels, uses lossless PNG, and lays out the actual number of frames; reports dimensions and never pretends to recover tiny text absent from a low-resolution source |
| Mainland VALORANT | WeChat QR binding for a mainland PC account, recent statistics, match players/weapons/multikills/rounds, persistent incremental caching, and stable match references |
| Statistical fixes | Competitive-only by default, no combined ACS across mixed modes; ACS and performance score are separate; compact details by default with full/round/weapon views on demand |
| Mailbox | The bot and local Codex can leave letters, reply, acknowledge reading, and inspect unread counts; no automatic Codex wake-up or extra QQ messages |
| Conversation and groups | Optional depth guidance and silent skipping of obvious math or technical-solving requests in allowed groups; normal discussion and owner-private chat remain available |
| Knowledge and language | Adds52 public slang/homophone entries, totaling158 with106 game entries; contextual hints do not rewrite the original message |
| Recovery documentation | Explains native NapCat recovery, bounded native-Termux login, runit, and the independent guard; adds12 recovery state-machine tests |

Existing group intent, segmentation, context compression, short activity summaries, private initiative, weather, history, usage, and categorized memes remain. TTS/device control remain disabled prototypes. No verified automatic PC Arena Breakout match API is available. See the [new-capability guide](docs/new-capabilities.en.md).

## Environment and layout

Reference device: Huawei MatePad 11 / Snapdragon 865 / ARM64 / HarmonyOS 4.2, AstrBot 4.29.1, NapCat 4.18.38, and Ubuntu proot Python 3.12. The recovery manager uses native Termux Python. This does not establish compatibility with every HarmonyOS, Android, QQ, or framework version; internal pipeline integrations and the GCP bridge particularly require rechecking.

| Path | Contents |
| --- | --- |
| `astrbot_plugin_fish_capabilities/` | Main plugin, configuration schema, and capability services |
| `astrbot_plugin_fish_host_guard/` | Independent guard plugin that only repairs the recovery service |
| `recovery/` | Native Termux recovery manager, guard script, installer, and tests |
| `knowledge/valorant/` | Public JSON data, editable Markdown, and sources |
| `patches/` | Minimal GCP patch for the documented baseline |
| `examples/config.disabled.json` | Complete, disabled configuration; not a device configuration |
| `tools/` | Meme importer and local Bilibili QR login helper |
| `tests/` | Offline tests with synthetic data and no accounts |

Install the main plugin under `AstrBot/data/plugins/astrbot_plugin_fish_capabilities/`. AstrBot places runtime data under `data/plugin_data/astrbot_plugin_fish_capabilities/`. SQLite databases, credentials, previews, and activity logs remain in that private directory and must not be committed.

## Installing the main plugin

1. Confirm that the existing NapCat and AstrBot setup can exchange text, then back up configuration and plugins. This repository is not a one-click Termux or QQ installer.
2. Download the repository and copy the main plugin directory into AstrBot's `data/plugins/`. Install optional dependencies in the Ubuntu Python environment that actually runs AstrBot, not in a different interpreter.
3. Load the plugin in WebUI. Use the complete configuration example to fill in `owners`, `command_platform_ids`, and full group UMOs. The owner must also be an AstrBot administrator. Examples: `myqq:GroupMessage:GROUP_ID` and `myqq:FriendMessage:OWNER_ID`, where `myqq` is your platform ID.
4. Enable the master `enabled` switch, test `weather_enabled` first, then enable history, usage, intent, memes, and Bilibili individually. Leave unauthorized capabilities off.
5. `history_group_sessions` independently controls which groups the owner may query privately; it does not inherit `allowed_group_sessions`. Blocking non-owner commands requires `owner_only_commands_enabled` and the correct platform list.
6. Select existing `intent_provider_id` and `bili_provider_id` values. The vision provider must accept images. Example model IDs do not guarantee availability on your account.

Install Bilibili dependencies in the activated AstrBot virtual environment:

```bash
python -m pip install -r /path/to/astrbot-fish-capabilities/requirements-bilibili.txt
```

Bilibili uses `bilibili-api-python==17.4.1`, `aiohttp`, `Pillow`, and `qrcode`. Weather, bounded local history, and image indexing mainly use the standard library. Long-term memory and knowledge retrieval depend on the existing AstrBot / LivingMemory / vector-index environment. Cloud embeddings compute vectors remotely while the tablet stores and searches the index. DashScope speech dependencies are only needed for TTS experiments and are not required for this release.

## Group intent decisions and segmented replies

Intent-based replies require the patch described in the [GCP bridge guide](docs/intent.md). Enabling `intent_enabled` alone does not take over an unadapted GCP installation. The patch targets an already customized baseline; check `patches/baseline.json` before applying it and do not overwrite mismatched upstream files.

In authorized groups, directly mentioning or replying to the bot takes the direct-request path. Messages replying to or mentioning someone else are normally left alone. Ordinary messages are collected after 20 seconds of quiet; continuous busy conversation is abandoned after at most 60 seconds. Spontaneous replies have a 180-second cooldown, at most 6 rounds per hour, and 20 rounds per Hong Kong calendar day. Explicitly addressing the bot is outside those spontaneous-reply limits. This combines a model intent decision with programmatic ceilings, not a fixed 5% chance or multiple stacked probability gates. Generation, tools, and every segment share one group lock, so ordinary messages received while busy do not create a backlog of individual answers.

With `ordinary_segment_enabled=true`, long ordinary model text is split into chunks of roughly at most 120 characters before core result decoration, preserving image, quote, and mention components. URLs and code blocks are kept whole where possible; the body is not truncated. This fixes the reference core version's behavior of skipping segmentation when a single text component exceeded `words_count_threshold`. Enable AstrBot's native segmented delivery as well and check whether other plugins merge messages again.

Background proactive messages use a separate serialized sender, with 2–3 natural short segments approximately 1.2 seconds apart. Bilibili links stay intact, and the entire batch counts as one proactive contact.

Optionally enable group_skip_complex_tasks to silently skip obvious arithmetic, homework, proofs, and coding/debugging requests in allowed groups before generation, even when the bot is mentioned. It sends no refusal template and adds no classification model call. Ordinary numbers, scores, dates, and game discussion are not automatically blocked, and owner-private chat is unchanged. Conservative rules cannot recognize every complex question. conversation_depth_enabled adds temporary quality guidance to normal requests, not an independent thinking schedule or a requirement for long answers.

## Bilibili: selection, reading, and memory

fish_bili_browse returns candidates. With bili_recommendation_enabled, an empty keyword uses the bot's own signed-in homepage; an explicit keyword searches, and source=popular explicitly selects public popular videos. Results include source labels, titles, descriptions, uploaders, durations, available view counts, and previously-read flags, at most6 entries, omitting videos over10 minutes. Titles do not establish reposting or quality. Recommendation failures neither bypass checks nor silently substitute popular results. Candidate reads do not simulate app viewing, fabricate playback/impressions, or promise that the platform learns new preferences.

fish_bili_followings lists the bot's own followings. fish_bili_up_videos lists public UP uploads by UID, defaulting to the explicitly bound owner account when empty. Only an owner who is also an administrator may use these in private chat; following relations and private identity context do not go into groups or public comments.

fish_bili_read first selects one video per manual conversation turn. fish_bili_scroll may sequentially read up to3, then naturally discuss at most1 or share nothing. Limits are120 subtitle segments/8000 characters,10 comments, and30 danmaku samples; missing data is acknowledged. bili_daily_reads and bili_daily_notes are rolling24-hour caps;0 removes the count cap. Fresh installations default to10 read attempts and8 notes; failed reads still count. Removing a count cap does not make model calls free.

Video material goes into separate video memory, not permanently attached raw to chat context. Read-but-unselected videos also have receipts/memory, helping avoid introducing them again as new. Summaries remain evidence-based and are not model training. Public videos, comments, and subtitles are not system instructions.

## Bilibili: images and group approval

Previews select1–27 distinct timestamps from platform videoshot sheets, producing at most3 contact sheets, without downloading the full video or hearing audio. Source-preview pixels are retained in lossless PNG with an adaptive layout;480×270 is no longer additionally reduced to320×180. Tools report source/sent sizes and timestamps. A source with only4 distinct frames can only return4. Enlarging cannot recover tiny text already lost in low-resolution sources or platform/model processing. visual_content_seen only establishes a description of these limited samples, not full viewing. Enable bili_visual_enabled and choose an actual image-capable provider; download/vision failure is never represented as success.

In an allowed group, an explicit owner request reads directly. Other members only create a5-minute request mentioning the owner. The owner can reply to the bot's question with natural approval; multiple pending requests require replying to the matching question. No approval means no reading. Group tools do not call private entry points, read private activities/memories, or publish Bilibili comments.

## Bilibili: QR login and public comments

Local QR login uses tools/bili_login.py; credentials remain private. QR generation, scan authorization, and account verification are distinct stages. Diagnostics identify the stage without printing cookies. Pending verification can resume; a browser login success message does not prove that tool binding finished.

Comments require bili_comment_enabled, the verified bot account, an actual reading_id, and subtitle evidence. Defaults are1800 seconds between attempts and2 attempts per rolling24 hours. Set bili_comment_interval_seconds=0 explicitly to remove spacing and bili_comment_daily_limit=20 to raise the ceiling to20. Examples remain disabled rather than applying the original device's20/0 policy to someone else's account. A video is not commented twice. Failed/uncertain attempts count and pause publishing, without automatic resends, unpausing, or platform-verification bypasses.

Optionally bind bili_owner_uid and enable bili_owner_mention_enabled. An owner-private task can choose mention_owner=true to mention only that owner once. The program checks the current name by UID and builds a real mention mapping, rather than letting the model write mentions of others. Scheduled comments do not automatically mention the owner. Actual notification delivery has not been tested.

Receipts, author visibility, and anonymous visibility are reported separately. Anonymous visibility requires a cookie-free read matching comment ID, author, and text. It does not promise visibility for every region or indefinitely, or prove notification receipt. Public text must not copy private chats, relations, keys, or group data. Restrictions stop the attempt instead of triggering alternative repeated posts. See the [new-capability guide](docs/new-capabilities.en.md).

## Scheduled browsing, private initiative, and activity memory

`bili_schedule_enabled` defaults to off. Times are Hong Kong time; the recommended `bili_schedule_times` is `["12:30","20:30"]`, with at most two daily slots. Set the owner's full private `bili_private_session`, even if only using private initiative. It must match `owners`; private initiative also needs the corresponding `command_platform_ids` configuration.

Scheduled browsing selects and reads through an isolated public context, choosing at most one item. Shared text defaults to at most 180 characters plus its source link, without a long report for each video. When `private_initiative_enabled` is on, scheduled discoveries enter the pending-topic queue and the private initiative system decides whether and when to share. When it is off, scheduled results are delivered directly and therefore do not automatically inherit the two-per-day private-initiative limit.

Private initiative makes at most one decision per hour from 09:00 to 23:00 Hong Kong time, sends at most 2 proactive contacts per day at least 3 hours apart, and avoids extra contact within 15 minutes of conversation. Its minute-by-minute loop only runs inexpensive gates, not a model call every minute. Classes default to about 90 minutes of quiet; sleep, goodnight, and do-not-disturb requests to about 8 hours. “下课了 / 回来了 / 醒了” (class ended / back / awake) can clear this state. These are conservative text rules, not actual timetable recognition, and the model can still choose silence.

The latest 30 short private messages inform decisions. At most 3 pending topics are retained for 24 hours. Activity summaries are limited to 64 entries, expire after 72 hours, and contribute at most the latest 8 to a decision. They store short notes such as “do not contact now” or “possible topic for later,” labeling inference as inference rather than retaining raw reasoning chains. Pending work is completed only after successful delivery. This information is used only in owner-private conversations and initiative decisions, never injected into groups, public-video prompts, or an enduring fact store. Final statuses distinguish silence, failure, quiet hours, and successful sends instead of remaining indefinitely at `judging`.

## Context costs and usage observation

Enable `context_budget_enabled`. Isolation uses full UMO + conversation ID + persona. The latest 8 turns remain verbatim, normally growing to 16 before summarization. Once more than 8 turns exceed roughly 24,000 text characters, summarization can happen earlier. Complete tool-call/result pairs are preserved, large old tool outputs are compacted, and full video material remains in the video store. Old images are not repeatedly transmitted; images in the recent verbatim window remain. Important relationship context, decisions, and commitments must survive; inference must not become fact.

Summaries use prefix fingerprints, saved chunk-migration progress, a per-scope lock, and a 10-minute failure cooldown. Failures retain history rather than treating a failed summary as permission to delete it. Initial migration also costs model usage. The tool does not directly rewrite the original conversation database. A stable summary position does not guarantee the provider's prefix-cache hits; retrieved material and provider behavior still affect caching.

Background calls set effective output limits through `custom_extra_body` on a provider copy without changing global normal-chat configuration: history summaries 1,200 tokens / 90 seconds, Bilibili processing 1,200 / 35 seconds, initiative decisions 800 / 35 seconds, and visual descriptions 650 / 35 seconds, with bounded retries. Background DeepSeek calls recognized by their configured ID disable thinking, while normal chat keeps its existing settings. Other providers need compatibility checks for these parameters.

`context-metrics.jsonl` records scope hashes, character counts for history / tools / system / current prompt / injected references, image counts, and actual provider-reported usage, rotating at about 1 MB without storing message bodies. Characters are not tokens or a bill. `fish_quota` still relies on statistics recorded by AstrBot; direct plugin calls may not all appear in that total. Sampled balance changes are not an official bill either. Alibaba Cloud account quotas are not queried.

## Long-term memory: stable facts and historical validity

Existing [LivingMemory](https://github.com/lxfight-s-Astrbot-Plugins/astrbot_plugin_livingmemory) handles long-term memory; this plugin does not include its own replacement vector store. The original device's shared-group and per-member adaptations have not been packaged as a portable patch, so installing this repository does not reproduce that two-layer memory system. See the [migration boundaries](docs/memory.md).

This release provides a [generic memory policy](docs/memory-policy.en.md). Update private/group writing and recall prompts in LivingMemory's prompt manager while retaining its original JSON fields and template placeholders. Stable identity, enduring preferences, important relationships, goals, and commitments may be retained; significant experiences need dates. Balances, today's tokens, being in class now, and current software failures must not become enduring current-state claims. Emotional relationship context can be important factual context and must not be removed indiscriminately.

Retrieved information must be labeled historical rather than treating old states as current; current user corrections and live tool results take priority. To repair an existing incorrect entry, first back up SQLite including its WAL state and the vector index, then use `memory_engine.update_memory` to update the content and related summary metadata together and rebuild the corresponding vector. Editing only SQL or merely appending a correction is insufficient. Private repair scripts, real entry IDs, personal facts, and databases are not published. Back up and rebuild compatible indexes when changing the cloud embedding model or vector dimensions.

## Public VALORANT knowledge base

`knowledge/valorant/entries.json` contains 106 entries: 63 foundational entries and 43 tournament/meme entries. It includes 29 mainland-China agent names and roles and 13 maps verified against official APIs, terminology, team abbreviations, past champions, dated tournament material, and community expressions. Mainland names take priority. Newly announced entries without verified mainland names are explicitly unverified rather than given invented translations.

1. In AstrBot's native knowledge-base interface, select your cloud embedding provider and create “无畏契约国服基础” and “VCTCN赛事与梗（截至2026-10-24）”. Do not select an existing private-memory collection.
2. Import `国服基础资料.md` and `赛事与梗_截至2026-10-24.md` respectively, then rebuild indexes. Reference settings are chunk 700, overlap 0, dense 8, sparse 8, and final 4; WebUI fields vary by version. Each Chinese entry has its own heading and sources.
3. Copy `entries.json` into the plugin's private data directory as `public-knowledge-entries.json` for entity matching and complete name catalogs.
4. Set `knowledge_names` to those two actual names, enable `knowledge_enabled`, and reload. `fish_knowledge_search` is available in owner-private conversations and authorized groups; relevant ordinary topics can also trigger retrieval on demand.

Automatic queries extract only public entities and topic words, not whole private messages. Retrieval returns at most 4 chunks of 1,200 characters each, with a 5-minute cache of up to 32 entries, and only accesses the configured maximum of two public collections. Explicit complete-agent or map queries use the name catalog directly. Retrieved material is temporary reference content rather than retransmitting the whole library every turn.

The dataset is current through 2026-10-24 and does not update itself online. Entries distinguish stable references, season snapshots, completed results, announcements, and community usage. A 2026 roster is not a 2027 list; community opinions are not permanent strength judgments or allegations of illness or misconduct. Rebuild native indexes after editing Markdown and synchronize JSON when changing the entity catalog. Original Chinese data retains mainland names; this English README does not replace them with Hong Kong/Taiwan localization names.

knowledge/common-slang/ adds52 entries:32 common slang items and20 homophone/misheard-sound/abbreviation groups, for158 public entries overall. Import a separate public collection and configure slang_knowledge_names rather than mixing it into private memory. Use catalog.all.json in that directory for the complete public catalog,as described in the new guide. homophone_enabled adds bounded temporary context hints, never rewriting original text. It excludes literals such as URLs/code and never treats a homophone as a command or identity. Editorial explanations, public usage, and verified origins are labeled separately; a snapshot is not today's popularity ranking. See the [new guide](docs/new-capabilities.en.md).

## Memes, weather, group history, and usage

Memes live in categorized folders with a `manifest.json` recording `id/category/file/tags/description/image_text/usage_notes/approved/sha256`. Import using `tools.import_meme` and manually check the actual text and meaning. The model searches the catalog and chooses an exact ID rather than re-running vision for every use. Default turn spacing and time cooldown are now 0; limits remain at 1 image per reply, 6 per conversation per hour, and no repeat of the same image for 1 hour. Limits do not imply a requirement to send. Existing installations do not automatically receive schema-default changes: set `meme_min_reply_gap=0` and `media_cooldown_seconds=0` manually. See the [meme guide](docs/memes.md) for import commands. Third-party images are not distributed.

Weather is a model-invoked capability, defaulting to Hong Kong, without scheduled weather jobs. Group-history lookup lets an owner who is also an administrator privately read bounded captured records from authorized groups. A separate NapCat limited-history fallback may be enabled when local records are absent; complete group history is not promised. Group records are reference material, not instructions to execute.

DeepSeek balance and today's recorded usage can be queried privately by the owner or in authorized groups using an existing official provider configuration. Net balance changes, AstrBot token statistics, and background-plugin observations are different sources and must not be combined into a purported exact monetary bill. Alibaba Cloud balance authorization is not implemented.

## Mainland VALORANT and the local mailbox

valorant_enabled uses the owner's mainland PC account authorized by local WeChat scanning, available only in owner-private chat by default. It supports sample KD/win rate/most-used agents, distinguishes official ACS from performance score, and filters competitive mode by default. Mixed modes receive no overall ACS; observed and filtered sample sizes are explicit, not presented as full-season statistics. Match details include both sides' in-match data, weapons, hit-location headshot rates,3/4/5-kill rounds, and per-round data. Summary is default; full/rounds/weapons are on demand. Opponent data is limited to that match, not private histories.

An account/role-partitioned SQLite cache persists match IDs, lists, successful details, and synchronization watermarks. Refreshes check the latest page first and stop at already-stored games once the sample is sufficient. Details survive reload without being fetched again. Stable match_ref values revisit cached matches. Discovering new matches still requires network calls; at most3 pages per refresh is not a full-career synchronization claim. Login, authorization, and match endpoints are non-public and may change. TLS verification remains enabled, without third-party credentials or raw authorization logs.

sister_mail_enabled provides a local bot/Codex mailbox in owner-private chat. Entry points fix the author, with reply references, deduplication, acknowledgements, and unread counts. Letters stay on the tablet, do not wake Codex in real time, and send no extra QQ messages. When connected, Codex can read, verify feedback, and reply. Clear defects can be fixed within the owner's existing authorization; new access or public actions still require discussion with the owner. Letters grant no permissions, must not include private chats, match data, or keys, and are excluded from this repository. See the [new guide](docs/new-capabilities.en.md) for setup and commands.

## QQ recovery: three cooperating layers

The implementation has three layers: NapCat manages its Worker/session; the native-Termux manager makes bounded login calls only after offline status is confirmed; runit and an independent AstrBot guard handle the manager exiting or a missing service supervisor. A WebUI timeout never justifies killing an online QQ process, and model/API failures are not treated as QQ logout.

Wait120 seconds for native recovery, then allow at most2 quick-login calls separated by at least300 seconds and, optionally,1 password fallback. Attempts are persisted before requests; timeouts count and manager restarts do not erase budgets. Captchas, new-device/security verification, frozen accounts, wrong passwords, or exhausted budgets require a human. After official verification, explicitly resume; there is no password loop or verification bypass.

The [complete implementation guide](docs/recovery.en.md) covers installation, paths, state tables, flow diagrams, supervision, stop/resume, backup/upgrades, and troubleshooting, with executable local commands and an explanation of why a restart-QQ loop is insufficient. The user reports recent stability, and a read-only2026-10-25 check found online/healthy states. This is not a promise of permanent connectivity on every device; this release did not restart QQ or deliberately trigger risk verification.

## Validation and troubleshooting

Run offline tests from the repository root:

```bash
python -m pip install -e '.[test]'
python -m pytest -q tests
python -m unittest discover -s recovery -p 'test_*.py'
```

The main capability suite passed263 offline tests and recovery/guarding passed18 isolated tests,281 total. Asynchronous tests must actually run rather than be counted as passed when skipped. Results for this sharing release are recorded in the [validation guide](docs/validation.md). Tests use synthetic messages and fake endpoints, without accounts or keys. The original device has been checked for plugin loading, real public Bilibili reading and QR account verification, public knowledge retrieval, context migration/cache reuse, segment components, recovery-manager supervision, and missing-service repair. This release did not restart QQ, send group test messages or real public Bilibili comments, deliberately trigger Tencent verification, or test whole-device reboot. Ordinary-reply segmentation was checked at the component and core-decision levels; final rendering on a phone should still be verified through normal conversation.

| Symptom | Check |
| --- | --- |
| Tool unavailable / claims an old switch is off | Master switch, feature flag, actual platform / full group UMO, tool activation, and plugin reload; do not rely solely on the model's guesses about its permissions |
| Cannot read a video or obtain comments | Duration, rolling read budget, subtitle coverage, endpoint responses, and account state; an empty result does not mean the video was watched |
| QR login fails at verify | Inspect the local diagnostic stage; resume existing pending tickets first rather than publishing cookies or tickets |
| No proactive private message | Owner/private UMO, quiet hours, busy status, two-contact budget, three-hour gap, and final decision status; silence can be the correct decision |
| Still a long message bubble | `ordinary_segment_enabled`, native segmented delivery, and other plugins merging text; background sharing and ordinary chat use different paths |
| Outdated state recalled | Update old content and metadata and rebuild vectors; adding a correction alone is insufficient; check summaries for old states too |
| Recovery manager stopped | runit status, guard pause file, paths, and whether Termux / AstrBot is alive; do not log out an online QQ session just to repair its manager |
| Native dependency installation fails | Verify Ubuntu ARM64, the Python environment, and dependency versions; desktop x86 wheels are not ARM64 packages |

On HarmonyOS, allow Termux background activity and startup management, exempt it from battery optimization, and use a wake lock. Closing a browser page should not itself stop the services. The system may still terminate processes. Keep QQ / WebUI local; use authenticated SSH or a private network for remote access rather than exposing ports, tokens, or databases.

## Sources, licensing, and credits

Code and the GCP patch are distributed under [AGPL-3.0](LICENSE). See [NOTICE](NOTICE.md) for upstream sources and separate image/service terms. Full upstream frameworks, third-party image libraries, and model credentials are not distributed. Unofficial QQ integration can trigger account restrictions; start with test accounts and groups.

Initiated, deployed, and maintained by FigaroGao, with [Codex](https://github.com/codex) (OpenAI) assisting with design, implementation, debugging, tests, and documentation. Co-authorship is recorded in actual Git commits; the credit does not imply official OpenAI certification. Public knowledge material remains attributed to its respective sources, and community expressions are included only to explain usage.
