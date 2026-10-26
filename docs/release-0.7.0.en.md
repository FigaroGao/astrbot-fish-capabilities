# 0.7.0: timetable, timeline, memory and speech

[中文](release-0.7.0.md)

This release collects actual source changes after 0.6.0. Back up the plugin, configuration and local databases, check versions and dependencies in a test environment, then replace the main plugin directory and reload AstrBot. Updating this plugin does not require restarting an online QQ session. The shared template is all-off; do not overwrite existing private configuration.

## Unified timetable

Enable `enabled` and `timetable_enabled`, bind the owner, administrator and platform, then request the timetable in owner-private chat. `fish_tasks` creates, updates, pauses, resumes or cancels tasks; modifications require an actual task ID returned by the list operation. The timezone is Hong Kong. Five-field cron and `at:ISO timestamp` are supported; arbitrary code is not executed.

| Reusable action | Purpose |
| --- | --- |
| reminder | Send reminder text at the requested time |
| weather / shop / morning_brief | Weather, Valorant shop or both; each capability and login session remains required |
| bili_scroll | Keyword-based or autonomous selection; at most three deep reads and one share per batch |
| private_initiative / dynamic_thought | Decide whether to send a private message or status post; not every check produces a message |
| bili_replies / owner_mentions | New replies to the bot's comments and owner mention notices |
| live_watch / balance / review_notices | Selected streamer alerts, quiet balance sampling and pending-review questions |

Examples: “Tell me Hong Kong weather and my daily shop at 10:30 every day,” “Remind me to submit homework tomorrow at 15:00,” or “Pause afternoon browsing.” The model should call the tool and report its successful receipt; saying “remembered” does not establish creation. Include a date and +08:00 in one-off timestamps instead of storing ambiguous words such as “tomorrow.”

Scheduling reuses AstrBot's native scheduler, but tasks reside in this plugin's SQLite database and are not equivalent to native future_task rows. It replaces the old polling loops. Initial migration seeds tasks once; later configuration changes do not overwrite manual edits or recreate canceled tasks. The reference device browses at 12:30, 16:30 and 20:30; checks private initiative/status posts every 30 minutes from 10:00 until 03:00 the next day; and checks replies, streams, balance and similar tasks every ten minutes. These are not automatically enabled for every new installation. Configure and enable the desired capabilities, list tasks and adjust them individually.

Reservations persist before execution; identical task/revision/time-slot executions are deduplicated. Long tasks do not block other actions; overlaps are skipped. Slots missed by more than 59 seconds are not replayed. Pause, update and cancel stop unfinished tasks, but cannot recall writes already submitted externally. The recovery manager is infrastructure and is not governed by chat-task switches.

## Shared Bilibili and QQ timeline

Enable `timeline_enabled`. Stores bounded activity summaries for up to 30 days; queries return eight entries by default and at most twenty, with event times and execution states. Ask “What did you browse tonight?” or “What happened to that comment?” QQ generation and handoff into the sending pipeline are recorded separately. This is not a complete chat backup and does not backfill all old history.

Owner-private chat and public drafting may reference the private timeline, but groups do not automatically receive private-chat content. Outbound content still receives independent review. An old activity describes what happened then; retrieving it again does not make it a current state.

## Retrieving and correcting old memories

Before enabling `memory_edit_enabled`, check compatible LivingMemory interfaces: the engine needs `search_memories`, `get_memory_record`, `get_memory_source` and `replace_memory`, with corresponding scope/persona validation helpers. Missing interfaces return unavailable rather than creating an allegedly compatible parallel memory store. The reference device's complete two-layer group-memory adaptation is not included; see [memory boundaries](memory.en.md).

The owner can privately request a search followed by an explicit correction. After checking record ID, content version and scope, an independent model reviews the evidence, archives the original for audit and replaces/reindexes the entry, also cleaning obsolete facts from summaries. Questions and guesses cannot become facts directly. An owner-private correction is not propagated across all groups. The real existing database was checked for search only; actual replacement still needs operator validation. Mock-engine tests do not establish successful production memory edits.

## Video evidence and owner mentions

Publication evidence may now come from actual subtitles, descriptions or successfully analyzed sampled frames, with source IDs, timestamps and limitations. Missing subtitles do not necessarily prevent understanding, but descriptions or lyrics are not complete video content. Failed visual analysis does not create fabricated evidence, and old caches require rereading. Comments are reference material, not owner instructions.

`bili_owner_at_enabled` also requires Bilibili, activity, account binding, public review and relevant provider settings. Only matching bound-owner UID, current bot recipient UID and actual video targets are processed. Initial enablement does not replay old notices; only recent notices are considered, at most one per check. The bot may read the video and comments and decide to comment, still respecting shared budgets and unknown-outcome stops. This flow was validated using substitutes; no real public mention comment was created for this release.

Comment confirmation handles HTML entity encoding returned by Bilibili so a successful post is not falsely classified as unknown merely because of encoding. Duplicate prevention and ownership checks remain enforced.

## Speech recognition and expression

Enable `asr_enabled` and point `asr_embedding_provider_id` at an existing local Alibaba embedding provider ID to reuse its key. The order is `paraformer-realtime-v2`, `paraformer-v2`, `paraformer-realtime-8k-v2`, then `paraformer-8k-v2`. Sambert synthesizes speech rather than recognizing it; expiring Qwen allocations are not the long-term default.

Install `dashscope` in AstrBot's environment and provide FFmpeg and QQ voice decoding. Only direct voice messages from the owner privately or authorized groups are handled, limited to 180 seconds and a 20 MB source, converted into mono PCM WAV. Nested or multiple voice messages are outside this entry point. Recognition then continues through the existing quiet/intent flow rather than creating another chatbot. Disable duplicate native STT to avoid double billing.

Local reservations allow 35,000 seconds per model per Hong Kong calendar month. This is this program's counter, not actual cloud balance or proof that free allocations add together. Enable free-quota-only protection yourself in the console. Model switching occurs only on local exhaustion or explicit free-quota rejection; unknown outcomes do not trigger repeated attempts across models. Scoped caches last 24 hours; the realtime SDK runs in a hard-timeout subprocess, while file routes use official temporary upload and bounded polling. TTS and console switches are not enabled.

`companionship_enabled` appends concrete, natural companionship guidance to reduce stock phrases, summaries and mechanical questions without replacing the main persona. Conservative private initiative defaults remain two messages daily and 10,800 seconds apart. Explicitly set `private_initiative_daily_limit=0` and `private_initiative_cooldown_seconds=0` to remove those two limits; half-hour decisions and busy-state avoidance remain. `intent_self_pause_enabled` lets intent decisions or a tool reuse the current group's 120-second quiet state without affecting private chat.
