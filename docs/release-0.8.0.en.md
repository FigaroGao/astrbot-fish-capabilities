# 0.8.0: Companionship, observability, and selective video reading

[中文](release-0.8.0.md) · [Deployment and validation](deployment-20261027.en.md)

2026-10-27. The reusable capabilities below are now in the shared source. They were deployed individually on the reference tablet with its owner's authorization; shared configuration still disables all capabilities and leaves identities empty. This is not a copy of a private instance. Reference-device tests do not guarantee installation on arbitrary devices.

## Twenty capabilities and entry points

| Capability | Behavior and limits |
| --- | --- |
| Memory provenance | Stores actual user quotations, attribution, and hashes; a quotation does not prove the model's interpretation. |
| Memory lifetime | Claims distinguish fact/state/event/inference/fiction; temporary states default to 2 hours, at most 24, and inferences to 7 days. Old summaries remain historical rather than becoming new facts in bulk. |
| Memory correction | Version checks, supersedes, and audit history; updates retrieval/persona summaries and key facts, reusing upstream index rebuilding. |
| Layered recall | Expands candidates within the original scope, then allocates preference, topic, and experience slots. Requires the matching local LivingMemory adaptation and `recall_engine.fish_layered_slots`; installing this plugin alone cannot add it to arbitrary upstream versions. |
| Summaries versus experiences | Preserves upstream canonical/persona channels; facts are injected according to lifetime, while viewing insights and expression examples are stored separately. |
| Group-member impressions | Subjective candidates require actual statements in the same group and owner approval before injection for that member/group; expire after 7 days by default. |
| Five-factor intent | Content, interest, social fit, timing, and continuity use 0/1/2 values; zero social fit or timing means silence. Stores decision metrics, not full reasoning. |
| Stale-answer review | Before first delivery, a new direct question can replace an unsent draft; ordinary changes get limited review. Once splitting starts, it does not repeat judgment; mute is checked again. |
| Proactive-contact candidates | pending/deferred/dropped/reserved/sent/expired; may defer or drop, with optional unanswered-message backoff. Does not restore the former two-per-day/three-hour hard limits. |
| Unified activity decisions | Busy autonomous activities can defer persistently for at most one hour. Failed or uncertain external actions are not replayed; explicit reminders, weather, and shop reports cannot be canceled by the model. |
| Contextual expression examples | Owner-approved positive/negative examples are temporarily recalled in small numbers by scene; example experiences do not become shared experiences. |
| Correctable observations | Observations, preferences, and expressions are separate, with version-conflict protection and audits. A passing mood is not made permanent. |
| Viewing insights | `fish_bili_reflect` and autonomous browsing save subjective observations supported by actual reading/evidence IDs. They can be corrected or archived; this does not train the model or automatically rewrite its persona. |
| Sharing feedback | Video selection uses previously read BV IDs and the owner's current explicit attitude, not private shelves, silence, or unanswered messages. |
| Video cover wall | Read videos, notes, reading scope, and receipts; fills up to 6 missing public covers per operation without rereading videos or calling a model. |
| Semantic meme library | Incremental vector indexing of reviewed descriptions, image text, and tags; only changed descriptions are rebuilt. No repeated image recognition; sending limits and public review remain. |
| Incremental group digest | `fish_group_history` defaults to summary, processing batches of 80 locally captured messages. Raw mode verifies local IDs; failures do not advance the cursor. |
| Unified permission registry | `capability_registry.py` centralizes switches and owner-private/authorized-group boundaries; existing command gates and independent public review remain. |
| Usage and latency | Displays actually recorded tokens, cache usage, and latency. Character categories are estimates, unknown costs remain unknown, and Alibaba Cloud quota is not queried. |
| Isolated simulation | Rule replay by default, optionally one intent-model preview. Never enters real delivery, writes to QQ/Bilibili, or changes real group state. |

Management: AstrBot dashboard → Plugins → capability extension → View → companion. Six tabs cover videos, expressions/observations, memes, timetable/permissions, usage/decisions, and simulation. It reuses AstrBot administrator authentication and opens no extra port. `fish_meme_search` finds candidates, `fish_learning` records explicit feedback, and `fish_usage_details` is owner-private only.

New switches include `learning_enabled`, `group_learning_enabled`, `group_digest_enabled`, `companion_dashboard_enabled`, `private_unanswered_backoff_enabled`, and `task_intent_gate_enabled`, all disabled by default. `meme_embedding_provider_id` is an AstrBot provider ID, not a key; when empty it can reuse `asr_embedding_provider_id`. Models use separate index namespaces. Full two-level group memory and local LivingMemory customizations are still not a generic patch installer.

## Expression, names, and joining conversations

The reference instance's primary name is 小鲸 (Xiaojing); older names such as 大肥鱼 are nonexclusive. `bot_primary_name` and `bot_nonexclusive_names` default to empty and must describe your own instance. Actual mentions, quoted account IDs, and context take precedence over matching name text. The private full persona and QQ identity are not distributed.

`tone_diagnostics_enabled` offers read-only diagnostics. Actual utterances help distinguish casual chat, emotional sharing, explanation, steps, comparison, and data. Rules locate empty agreement, unsolicited selection of one key point, negation-and-pivot patterns, framing/list endings, clustering within about 100 characters, and repeated openings across the last 5 records. Quotations, code, links, paths, and numbers are protected. Rules are not banned phrases or a humanlikeness score; there is no automatic polishing, random imperfections, or extra model call. Automatic records contain only scope, hashes, rule positions/counts, and timestamps: 14 days and at most 2,000 records, with neither participant's original text. Owner-private `fish_tone_diagnose` or the dashboard supports manual checks; manual input is not persisted. Inspired by dsh-fish-tone's judgment layer, independently implemented in Python without copying its corpus or random-word logic.

`intent_live_batch_enabled` addresses busy groups never reaching a quiet interval. The reference waits 6 seconds, with a batch after at most 12 seconds of continuous conversation. Ordinary follow-ups can merge; new direct questions, endings, topic changes, or explicit speech to someone else still cause a skip. The reference autonomous limits of 180 seconds, 6 turns/hour, and 20/day were not removed. Mute and pre-delivery review remain.

`meme_opportunity_enabled` locally supplies at most 3 approved images in verified owner-private casual, greeting, or emotional contexts. The model can select one or none, without another vision, embedding, or selection-model call. It respects requests for no images and does not mechanically decorate formal steps/data. Existing one-image-per-turn, six/hour, and repetition limits remain. A synthetic on-device example selected an image, which does not guarantee selection in every real conversation.

## Autonomous Bilibili comments and media

With `bili_comment_autonomy_enabled`, ordinary comments/replies can be sent after independent review without asking the owner one by one. Tasks, private matters, unavailable review, or uncertainty cause a skip rather than a QQ approval request. Old pending comments are neither notified nor replayed. Dynamic-post review is independent. The reference retains 20 comments per rolling 24 hours and a zero-second interval, with deduplication, account checks, and stopping after uncertain outcomes.

Root comments previously lacked a media directory for the model. They now reuse `CommentMedia.opportunity(context)`: at most 25 account-available site emotes and 6 approved public-library images, matched locally by description. Failures of the two sources are independent, with no extra selection model. Root comments and nested replies share the opportunity path, allowing at most one image/two emotes. The on-device directory worked, and tests intercepted selection and sending arguments. No public image was posted for testing, so visible publication is unverified.

## Selective video reading and characters

`bili_storyboard_enabled` first obtains at most 54 sparse preview candidates from up to 6 source sheets, creating an addressable overview with timestamps. The model can select actual IDs, normalized crops, or at most two windows of up to 60 seconds each. Ordinary detail viewing still selects available previews rather than arbitrary high-resolution source frames.

Only explicit promotion candidates with confidence ≥0.9 and valid endpoints are removed as ads. Up to 3 replacement positions may be added, with at most 27 overview frames. A brand name alone is insufficient. Zhuanzhuan, Miaojie, Aihuishou, and Qimao are sourced examples, not a blacklist. There is no real-ad accuracy benchmark.

`bili_gallery_scan_enabled` attempts normally authorized playback streams for slide/chat or highly repetitive videos. ffmpeg must be executable in AstrBot's environment: `pkg install ffmpeg` on Termux; install ffmpeg and add it to PATH on a computer. No audio is requested. HTTPS media-domain allowlist; at most 96 MiB download/60 seconds; single-thread decoding/90 seconds; videos at most 10 minutes; one sample every 0.5 seconds; maximum 1280 preserving aspect ratio without upscaling; temporary frames at most 128 MiB; at most 48 pages, read in batches of 6 separate images. Conservative pixel comparison may retain duplicates to avoid losing new text. `read/partial/unreadable/advertisement` retain distinct evidence and limits, and temporary media is cleaned up. Failures fall back to previews. Reading every discovered page does not guarantee coverage of brief flashes or every image/text in the video.

Inspired by [DSH storyboard](https://github.com/SAOS-3624/dsh-video-storyboard)'s addressable-overview → selected-detail approach. Its full scene-change/HSV/sharpest-frame algorithm was not implemented, and DSH was not installed.

`bili_character_enabled` loads local `character-atlas/cards.json` and up to 3 priority images, checking paths, suffixes, 8 MB limits, and SHA256. Matching shares the existing overview call. Results require valid frame IDs, visible evidence, and confidence ≥0.85; ad frames are filtered. Initial references are the DeepSeek maid whale, GPT white dragon, and orange-haired Claude with a book. Appearance does not prove an account, and not every whale is Xiaojing or every GPT is the sister. `examples/ai_character_atlas` contains cards/links only. Obtain images under their source terms and retain attribution; image bytes are not redistributed with the code. Missing images are skipped, without claiming a complete installed recognition model or trained embeddings.

## Public Codex announcements

`codex_resets_enabled` and `fish_codex_resets` provide owner-private status/history/detail through fixed HTTPS endpoints at [codex.markets](https://codex.markets/docs/api), not official OpenAI or personal quota data. History allows 1–50 entries; details may use already cached Chinese translations without calling a translation model. SQLite caching lasts 15 minutes, with failure cooldown.

The unified timetable's `codex_resets` action can use `*/15 * * * *`. It silently establishes an initial baseline and notifies only newer IDs with newer timestamps. Sync must be live, fresh within one hour, non-stale, and error-free. Old backfills and abnormal future timestamps are ignored. Delivery is persistently reserved beforehand; uncertain receipts are not automatically retried, and exactly-once delivery is not promised. The shared package contains no reference task database and does not create this task for a new installation. The reference tablet has one Hong Kong-time task, without old-announcement or test QQ notifications.

## Upgrade, privacy, and sources

Back up source and local configuration; install dependencies in the same Python environment, merge schema switches individually, and reload the capability plugin when idle. NapCat need not restart. Obtain character artwork separately under appropriate terms. Browser sessions, owner IDs, persona, mailbox, memories, task databases, and private test reports are not uploaded. Shared examples do not replace existing schedules; reference nightly reflection remains at 05:00 Hong Kong time. See [deployment evidence](deployment-20261027.en.md), including the HTTP 412 limitation.

Other design references include [RememberYou](https://github.com/menglimi/astrbot_plugin_remember_you), [WaveMemory](https://github.com/vivy1024/astrbot_plugin_wave_memory), [Heartflow](https://github.com/advent259141/Astrbot_plugin_Heartflow), [Aurabot](https://github.com/accomplish07zrh-eng/dsh-aurabot-qq), [bili-humanism](https://github.com/InariNGT-Ofiicial/dsh-bili-humanism), [Meme Manager](https://github.com/anka-afk/astrbot_plugin_meme_manager), [Mnemon](https://github.com/omdsh-dev/dsh-mnemon), [bili-pod](https://github.com/nullifyi/dsh-bili-pod), and [dsh-fish-tone](https://github.com/MX3a48c5/dsh-fish-tone). New services are independently implemented; LivingMemory customizations retain upstream licensing. A design reference does not imply interchangeable frameworks/plugins. Image terms are recorded in the cards and are not replaced by this project's AGPL.
