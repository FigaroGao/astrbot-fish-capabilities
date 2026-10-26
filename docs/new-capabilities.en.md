> 0.7.0 update: this page retains earlier capability instructions. For the unified timetable, 30-minute decisions from 10:00 until 03:00 the next day, optional removal of private-message limits, and description/actual visual evidence for comments, use the [new release guide](release-0.7.0.en.md). The older subtitle-only restriction below is superseded.

# New0.5.0 capabilities: configuration and use

[中文 — 完整对应版本](new-capabilities.md)

Install the main plugin and optional dependencies as described on the homepage. These features require enabled=true,correct owners/command_platform_ids,and AstrBot administrator identity. Leave unused switches false. Never copy the original device's accounts,keys,configuration,databases,letters,or memories. These are shareable setup instructions,not a device export.

## Bilibili homepage,followings,and UP uploads

After local QR login and account verification through tools/bili_login.py,enable bili_enabled. bili_recommendation_enabled=true makes empty-keyword/free browsing use the bot's own account homepage,not the owner's. Explicit keywords still search; source=popular selects popular results. Recommendation failure stops instead of disguising anonymous popular videos as signed-in recommendations. Read-only candidate requests do not guarantee that the platform learns new interests from this tool.

fish_bili_followings returns up to6 own followings. fish_bili_up_videos reads recent public uploads by exact UID. Configure bili_owner_uid locally to default an empty UID to the owner. Verify ownership of the actual profile,not just a nickname. Candidates include uploader,duration,publication time,and available views; statistics do not establish quality,reposting,or clipping. Videos over10 minutes are not deeply read.

Scheduling remains the configured Hong Kong12:30 and20:30 slots. Changing candidate sources adds no jobs. The model considers its existing interests and need not read the whole homepage; it may choose/share nothing. No automatic playback,likes,coins,or favorites are sent.

## The owner's public shelf

Separately enable bili_public_shelf_enabled. Read only when the current owner message explicitly asks to inspect public likes/favorites; a negative request does not read. fish_bili_public_shelf(kind=likes) lists recent public likes; folders lists public folders; favorites with folder_id selects a public folder's contents. limit is at most6 and page at most5. The endpoint may expose only limited recent entries; empty/partial output is not a basis to invent history.

Only anonymous public endpoints are used. A folder must appear in the bound owner's public list and explicitly be public; ownership and visibility are checked again on the content response. Video fields are limited to title,uploader,BV,and duration,without like/favorite times. Lists are not written to separate video memory or used as recommendation seeds. After a shelf read,the same turn cannot trigger automatic recommendation selection. The existing long-term-memory integration skips tool-loop summaries and instructions prohibit deriving owner-taste facts from the shelf. Ordinary conversation records remain framework-managed; this is not a claim that no conversation is retained anywhere.

No group access,private folders,messages,follower backends,or privacy changes. If the owner later explicitly selects a public video,normal10-minute/evidence rules still apply.

## Comment policy and mentioning the owner

Sharing defaults remain bili_comment_interval_seconds=1800 and bili_comment_daily_limit=2,with every writing switch off. After explicit owner authorization,spacing may be0 and the rolling24-hour ceiling up to20 attempts. Failed/unknown outcomes count and existing history is not erased. A video is not commented twice; uncertainty pauses publishing,without repeated retries or automatic unpausing.

To mention the owner,verify and configure bili_owner_uid locally,optionally record bili_owner_name,and enable bili_owner_mention_enabled. The comment tool's mention_owner=true selects that single bound target. The program rereads the current name by UID and attaches a real mention mapping; do not write raw@names in the text. Failed name/ownership checks stop the post. Scheduled comments do not automatically mention. A receipt,author visibility,anonymous visibility,and notification receipt are different conclusions. Actual notification delivery has not been tested or promised.

An actual reading_id,valid subtitle evidence_ids,and a match between the signed-in and bound bot account remain mandatory. A video without subtitles cannot manufacture posting evidence from images or comments. Inspect current budgets,spacing,and pauses with fish_bili_status rather than relying on old values in model context.

## Mainland VALORANT WeChat binding

Before enabling valorant_enabled,the owner locally authorizes their own mainland PC account through WeChat. Run the repository helper in AstrBot's Ubuntu virtual environment. Replace REPO with its real location and never point ASTRBOT_ROOT at a different installation:

```bash
export ASTRBOT_ROOT=/data/data/com.termux/files/home/AstrBot
cd "$ASTRBOT_ROOT"
REPO=/data/data/com.termux/files/home/astrbot-fish-capabilities
.venv/bin/python "$REPO/tools/valorant_wechat_login.py"
```

Open the printed random-path127.0.0.1 page,scan/confirm with the matching WeChat account,then verify the role in the terminal and type yes before binding is saved. The helper enables valorant_enabled; reload the capability plugin afterward. The original device's fish-val-login is a local shortcut,not a command automatically installed by copying this repository. Direct execution above does not require it.

WeChat long polling differs from ordinary requests:it waits up to35 seconds and a wait timeout means continue waiting,within an approximately180-second overall loop. Authorization exchange is not replayed automatically. Both JPEG/PNG QR images are supported and browser access logs are disabled. Diagnostics only store stage,exception type,duration,and numeric state,not codes/UUIDs/URLs. If exchange succeeded but role verification failed,a private pending file allows resumption. QR authorization alone does not prove match access.

Credentials are private valorant-wechat.credentials.json,pending verification is valorant-wechat.pending.json,and neither is committed. Third-party endpoints can change; TLS verification stays on. Multiple ambiguous roles are rejected instead of guessed.

## VALORANT statistics,details,and caching

fish_valorant_records defaults to3 matches,at most5. fish_valorant_profile defaults to competitive games within the most recent20 observed matches,at most30 observations,with all/unrated/deathmatch alternatives. It reports observed/filtered counts and mode proportions rather than fetching an entire career to fill the filtered count. Mixed/deathmatch modes get no overall ACS. score_avg is the ACS field; performance_score is a separate score. KD uses cumulative kills/deaths from valid KDA entries,without invented ratios for zero deaths or missing fields. A recent sample is not an official complete-season statistic.

fish_valorant_match accepts recent_index1–30. summary defaults to compact information about the owner and the top2 other players on each side,without every round. Choose full/rounds/weapons on demand and top_players0–5. Lists/details return match_ref for stable revisits; arbitrary other players' match IDs cannot be queried.

Details may include both sides' in-match KDA/agents/ranks/scores,the owner's hit-location headshot rate,weapons,head-to-head,and rounds.3/4/5-kill counts mean exactly3/4/5 kills in a round,excluding the global-summary row and not counting higher kills repeatedly in lower categories. Incomplete rounds do not become guessed zeros. Opponents are limited to visible data in that match,not private histories.

valorant-matches.sqlite3 partitions by account/role and persists match IDs,lists,successful details,and sync watermarks across reloads. New-match discovery still checks the head page and stops after encountering stored games with a sufficient sample. Details are filled on demand,not all20 re-fetched every time. At most3 pages is not full-career synchronization. There is no purchase,top-up,profile editing,or posting,and no claim of controlling every companion-app feature.

## The bot/Codex local mailbox

With sister_mail_enabled,the model in owner-private chat can use fish_sister_mail leave/read/ack. Letters are at most1200 characters,with24-hour deduplication for identical body/author/reply references. Reading starts at the oldest unread letter and reports total unread plus the count not shown on this page. A leave receipt means saved and waiting to be read;lack of automatic notification is not a save failure.

A local operator can use tools/sister_mail.py inside Ubuntu to read/reply,with the same ASTRBOT_ROOT. Never put actual content in command arguments or public logs; use a private text file for replies:

```bash
.venv/bin/python "$REPO/tools/sister_mail.py" list
.venv/bin/python "$REPO/tools/sister_mail.py" list --all --limit 10
.venv/bin/python "$REPO/tools/sister_mail.py" reply --text-file /private/reply.txt --reply-to 1
.venv/bin/python "$REPO/tools/sister_mail.py" ack 2
```

The original device's fish-sister-mail is also just a shortcut. Private data lives in sister-mail.sqlite3. Entry points fix authorship; the bot cannot impersonate Codex. Letters do not wake Codex in real time,send extra QQ messages,or create a persistent cross-model service. Codex verifies feature feedback rather than treating a letter's claims as new permissions. Never copy private chats,match data,UID associations,or keys into letters or this repository. Disable and reload to stop the feature; the database remains local.

## Language and public knowledge

knowledge/common-slang contains52 public entries,separate from106 game entries. Import it into a native public collection and configure slang_knowledge_names; game collections remain in knowledge_names. Copy knowledge/common-slang/catalog.all.json,the merged catalog of106 game and52 slang entries,to the private data directory as public-knowledge-entries.json for entity/alias hints. Back up an existing customized public catalog and merge by id rather than losing its entries. Enable knowledge_enabled for on-demand retrieval; rebuild cloud-embedding indexes after document changes.

homophone_enabled uses the packaged language_aliases.json for bounded hints without rewriting original text. URL/code/path literals are excluded. Hints assist understanding,not command authorization,identity changes,or private-data guesses. Public usage,editorial explanations,and verified sources remain distinct. Date snapshots instead of claiming every term is popular today.

group_skip_complex_tasks silently skips obvious arithmetic/homework/technical-solving requests in allowed groups while owner-private chat is unchanged; it cannot recognize every complex question. conversation_depth_enabled only adds temporary guidance to normal requests for grounded judgment and continuity. Casual messages may remain short,without invented offline experiences or consciousness growth.
