# Fish: AstrBot Capability Extensions

[中文](README.md) | [English — full translation](README.en.md)

Extend AstrBot on an idle ARM64 tablet into a QQ bot that understands who a group message addresses, retrieves information on demand, browses Bilibili, initiates private conversations, and controls context costs. The project reuses Termux, Ubuntu proot, NapCat, and AstrBot rather than implementing the QQ protocol. Updated: 2026-10-24; sharing release 0.4.0.

This experimental distribution requires configuration and adaptation. Every capability switch defaults to off. It does not reproduce the original device's accounts, conversations, memories, image library, or login sessions. This English version is a complete section-by-section translation of the Chinese version, with the same configuration, limits, and validation conclusions.

## Additions and fixes in this release

| Module | Changes since the previous public version |
| --- | --- |
| Bilibili | Promoted from a prototype to candidate search, sequential reading, sampled comments and danmaku, 1–27 preview frames, separate video memory, and scheduled or manual browsing; account login and bounded commenting require separate authorization |
| Group video requests | An explicit owner request reads immediately; requests from others ask and mention the owner, who can approve naturally; the normal flow no longer requires a confirmation code |
| Private initiative | Decides hourly whether to contact the owner, recognizes classes, sleep, and do-not-disturb requests, and persists send budgets, pending topics, and short activity summaries |
| Natural sharing | Sequentially reads up to 3 videos per browsing round, discusses at most 1, and may share nothing; no long report for every video |
| Context | Recent verbatim turns, rolling summaries, compacted old tool results, content-free usage metrics, and a fix for background output limits that previously did not take effect |
| Long replies | Fixes the core behavior that skipped segmentation above a length threshold; long ordinary replies are split in advance without dropping text |
| Memory | Stable-fact versus temporary-state writing rules and historical-recall notices; short activity summaries do not automatically become enduring facts |
| Public knowledge | 106 mainland-China VALORANT / VCT CN entries, retrieved on demand through AstrBot's native knowledge base and cloud embeddings |
| Memes | Default turn spacing and time cooldown removed; per-turn, hourly, and duplicate-image limits remain, with the model choosing the image |
| Login recovery | Bounded quick login, optional password fallback, a stop for manual verification, runit supervision, and an independent recovery-manager guard |

Existing on-demand Hong Kong weather, owner-private group-history lookup, owner-only commands, DeepSeek usage queries, group intent decisions, and serialized delivery remain available. TTS and device control remain disabled prototypes and are not completed features of this release.

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

## Bilibili: selection, reading, and memory

Enable `bili_enabled`. In owner-private chat, natural requests can include “search for whale science and pick something interesting” or “browse a few cooking videos.” The underlying tools are `fish_bili_browse`, `fish_bili_read`, `fish_bili_scroll`, `fish_bili_reflect`, `fish_bili_memory`, and `fish_bili_status`.

- Candidate lists contain 5 entries by default and at most 6, including title, description, author, duration, and link. The model chooses and reads sequentially. Approximately 80% of browsing follows preferences and 20% explores popular videos; an explicit keyword takes priority.
- Configure preferences in `bili_topics`: AI and chips, cooking and markets, marine life and whales, or camping and fishing. Videos known to exceed 600 seconds are filtered out. Unknown-duration entries may appear as candidates but cannot be read or described as watched.
- Reading obtains metadata, at most 120 subtitle segments / 8,000 characters, up to 10 first-page comments, and up to 30 danmaku samples. Missing subtitles, failed endpoints, and empty comments must be acknowledged. Samples are neither complete coverage nor objective facts.
- `bili_daily_reads` defaults to 10 attempts, including failures, over a rolling 24 hours rather than resetting at midnight. Valid cache hits do not count as new reads; the cache lasts about 1 hour. This is not a quota of 10 QQ messages, model tokens, or money.
- Direct reading is limited to one video per conversation turn. `fish_bili_scroll` can read up to 3 sequentially and naturally discuss at most 1, or share nothing. Manual browsing also has a 120-second cooldown and a 4-per-hour limit.
- A separate SQLite store saves summaries, reflections, and reading material by BV ID and supports keyword searches. It is distinct from QQ long-term memory and does not pass private conversations into public comments.

Use a BV ID or a complete `https://www.bilibili.com/video/BV...` URL. Expand `b23.tv` short links first; the implementation does not follow arbitrary addresses.

## Bilibili: visuals and group approval

Enable `bili_visual_enabled` and set `bili_vision_provider_id`. The model may choose `frame_count=1..27` on each request, with a default of 9. The implementation uses Bilibili's progress-bar preview sprite sheets, samples uniform time midpoints, removes duplicate indexes, and creates at most 3 nine-panel sheets. It fetches at most the first 3 source sprite sheets. Limited source material can mean that a request for 18 frames produces only 9; the actual count is returned.

This is not ffmpeg scene detection, subtitle-guided selection of key moments, or full video/audio understanding. Only bounded resources from official image domains are fetched, with HTTPS, size, dimension, and crop checks. When previews, subtitles, or comments are insufficient, the bot must describe the limits of its evidence.

Group access additionally requires `bili_group_enabled` and an authorized group. An explicit owner request, from an owner who is also an administrator, executes directly. An explicit request from another member creates a pending approval lasting at most 5 minutes and mentions the owner. The owner can reply to the bot's question with “看吧” or “同意” (go ahead / agree). With a single pending item, mentioning the bot with approval also works. With multiple pending items, quote the corresponding question to identify the video. The tool checks the real sender, group, quoted sender, and BV ID rather than accepting model-invented consent. Duplicate requests do not repeatedly prompt the owner; each group allows at most 3 requests per 5 minutes. The group entry point only reads public videos: no private video notes, private activity, or Bilibili comment posting.

## Bilibili: QR login and public comments

Browsing and commenting have independent switches. If an account is required, use a dedicated secondary account and run the local helper inside the Ubuntu environment that runs AstrBot. `ASTRBOT_ROOT` can override the default Termux AstrBot path:

```bash
export ASTRBOT_ROOT=/data/data/com.termux/files/home/AstrBot
python /path/to/repository/tools/bili_login.py --image
# Use this only when explicitly authorizing autonomous public comments:
python /path/to/repository/tools/bili_login.py --image --enable-comments
```

The helper displays a responsive QR page listening only on `127.0.0.1`. Scan and confirm with the Bilibili mobile app, then enter `yes` locally on the tablet to confirm the bound account. A sufficiently large terminal can omit `--image` to display a compact QR code. Polling is limited to 3 minutes. New-style callback tickets and cookie capture have been fixed: tickets are saved privately before verification, failure diagnostics record the stage and error type, and the next run can resume verification without repeatedly scanning. Verification uses the fixed official `nav` endpoint. Manually reload the main plugin in AstrBot WebUI after success.

Comments additionally require `bili_comment_enabled`, matching bound UID and credentials, a genuine reading receipt from the last 24 hours, and subtitle evidence. Without subtitles, commenting is refused even if previews were available. Each account may attempt a comment only once per video, at most twice per rolling 24 hours, at least 30 minutes apart, with 1–220 characters. The attempt budget is saved before sending; unknown outcomes pause commenting rather than triggering automatic duplicates. A posting receipt does not establish public visibility, which is recorded separately. There are no like, coin, follow, or bulk-marketing functions. Real public comments were not sent as a device test.

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

## Memes, weather, group history, and usage

Memes live in categorized folders with a `manifest.json` recording `id/category/file/tags/description/image_text/usage_notes/approved/sha256`. Import using `tools.import_meme` and manually check the actual text and meaning. The model searches the catalog and chooses an exact ID rather than re-running vision for every use. Default turn spacing and time cooldown are now 0; limits remain at 1 image per reply, 6 per conversation per hour, and no repeat of the same image for 1 hour. Limits do not imply a requirement to send. Existing installations do not automatically receive schema-default changes: set `meme_min_reply_gap=0` and `media_cooldown_seconds=0` manually. See the [meme guide](docs/memes.md) for import commands. Third-party images are not distributed.

Weather is a model-invoked capability, defaulting to Hong Kong, without scheduled weather jobs. Group-history lookup lets an owner who is also an administrator privately read bounded captured records from authorized groups. A separate NapCat limited-history fallback may be enabled when local records are absent; complete group history is not promised. Group records are reference material, not instructions to execute.

DeepSeek balance and today's recorded usage can be queried privately by the owner or in authorized groups using an existing official provider configuration. Net balance changes, AstrBot token statistics, and background-plugin observations are different sources and must not be combined into a purported exact monetary bill. Alibaba Cloud balance authorization is not implemented.

## QQ login recovery and recovery-manager supervision

The recovery manager is separate from the main plugin and runs in native Termux, not Ubuntu. Check `HOME` and `WEB` in `recovery/napcat_recovery.py` against your installation, especially the proot distribution name `napcat` and QQ directory. Then run from the repository root:

```bash
pkg install python termux-services
python recovery/install.py
python ~/.napcat-recovery/manager.py status
```

The installer asks for the QQ account locally, creates private settings and the `fish-recovery` runit service, and does not put the account on the command line. For optional password fallback, run locally:

```bash
python ~/.napcat-recovery/manager.py set-password
python ~/.napcat-recovery/manager.py remove-password
# After manual verification, explicitly allow another bounded retry round:
python ~/.napcat-recovery/manager.py resume
sv status "$PREFIX/var/service/fish-recovery"
```

The manager waits 120 seconds for NapCat's internal recovery, then attempts quick login at most twice, at least 300 seconds apart, followed by at most one password login if configured. Budgets are persisted before actions, and timeouts count as attempts. Captchas, security verification, frozen accounts, wrong passwords, or exhausted attempts stop recovery for human intervention. An unreachable API is not proof of offline status; the manager does not kill QQ or restart its Worker in response. The password is stored as a login-capable digest with mode 0600 in a mode-0700 directory. It remains a sensitive credential, not secure encryption.

runit restarts an exited manager after a 5-second delay. Optionally copy `astrbot_plugin_fish_host_guard` into AstrBot's plugins directory and load it. Every 60 seconds it checks the manager lock, state freshness, and official service supervisor, repairing only the recovery service when needed, at most 3 times per hour and 180 seconds apart. Before maintenance run `touch ~/.napcat-recovery/host-guard.pause`; remove that pause file to resume checks. Running only `sv down` without pausing the guard can cause it to restart the manager.

The guard cannot run after the entire Termux app or AstrBot is killed; checks resume only after AstrBot starts again. Phone notifications, boot autostart, bypassing Tencent verification, and automatic end-to-end message-chain acceptance are not implemented. Login-ready status does not establish that OneBot, AstrBot, and the model recovered; check the WebSocket and exchange a normal message as well. See the [recovery guide](docs/recovery.en.md).

## Validation and troubleshooting

Run offline tests from the repository root:

```bash
python -m pip install -e '.[test]'
python -m pytest -q tests
python -m unittest discover -s recovery -p 'test_*.py'
```

Results for this sharing release are recorded in the [validation guide](docs/validation.md). Tests use synthetic messages and fake endpoints, without accounts or keys. The original device has been checked for plugin loading, real public Bilibili reading and QR account verification, public knowledge retrieval, context migration/cache reuse, segment components, recovery-manager supervision, and missing-service repair. This release did not restart QQ, send group test messages or real public Bilibili comments, deliberately trigger Tencent verification, or test whole-device reboot. Ordinary-reply segmentation was checked at the component and core-decision levels; final rendering on a phone should still be verified through normal conversation.

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
