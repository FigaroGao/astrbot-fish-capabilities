# Share-release validation: 2026-10-26 · 0.7.0

[中文](validation.md)

The sanitized share directory was actually tested using pytest. With one new all-off/empty-identity configuration regression, **471 main-capability tests passed**, plus **18 independent recovery/watchdog tests**, for **489 total**. Host Python 3.11 emitted one audioop deprecation warning; the project includes conditional audioop-lts for Python 3.13, while the reference AstrBot environment uses Python 3.12. Tests use temporary directories, synthetic messages and interface substitutes, without real passwords or public posts.

New coverage includes task persistence, migration, deduplication, pause/cancel, long-task isolation and cross-midnight timing; timeline scopes, retrieval and redaction; memory-correction versions, scopes, audit and summary updates; owner-mention ownership, video evidence sources and HTML receipts; ASR reservation budgets, caching, timeouts and switching; group self-pause and disabled sharing defaults. Existing functionality tests continue to pass.

Earlier reference-tablet checks covered task migration/loading, real memory searches and activity records, audio conversion and four Paraformer routes, including successful recognition through the main hook and the 8 kHz file route. These do not establish fresh installations on every device or real QQ voice-message end-to-end delivery. No correction was written to real memories for testing; mock-engine tests do not substitute for that. This release did not manufacture a public owner mention, post comments/status updates, test a full-device reboot, trigger Tencent verification or restart online QQ.

Published material contains generic source, synthetic tests, all-off templates and public references only. Inspection of current files and visible Git history found no reported private nickname. Real bindings, keys, cookies, private persona prompts, chats, memories, letters, databases and runtime logs are excluded. New Chinese guides have complete section-by-section English translations. Offline tests do not establish real platform receipts, public visibility or final user delivery.

## Previous release validation (0.6.0)

# Sharing-release validation:2026-10-25 ·0.6.0

[中文](validation.md)

The sharing directory was retested with`python -m pytest -q tests`: **389 passed**;`python -m unittest discover -s recovery -p 'test_*.py'`: **18 passed**, for **407 total**. Tests use synthetic messages, temporary directories and fake endpoints, not real passwords or public comments. Dependencies are in the root`.[test]` extra. Asynchronous tests must run; skipping them because dependencies are missing is not a complete pass. The test platform label was generalized before publication and targeted tests were rechecked.

## Coverage in this release

Building on0.5.0 authorization, context, intent, knowledge, login, reading, match-record and cache checks, new coverage includes durable interaction deduplication, comment-thread ownership, independent review and fail-closed behavior, exact single-use approvals and question rejection, emotes and image-byte binding, calendar-day dynamic budgets, live-state transitions, daily-shop fields, nested-forward boundaries, and group silence, early resumption, automatic expiry and old-segment suppression. Counts come from actual execution rather than the number of added files.

Recovery retains12 state-machine tests and six independent-guard tests, covering waiting for native NapCat recovery, two quick-login attempts and one optional password fallback, pre-request persistence, counting timeouts, stopping for manual verification, waiting for QR without a password, unreachable WebUI, cooldowns and guard repair boundaries. The recovery manager itself is unchanged in this release. See the[recovery guide](recovery.en.md).

## Original-device reads and loading checks

Reference-device checks covered Bilibili account identity and favorite-folder ownership/privacy, interaction status, own-comment root/parent/ctime fields, independent text/image review, available emote and eligible image catalogs, following/reply/mention notices, selected-UP live state and background workers. Eight new knowledge chunks were imported into the original public vector index and requested-phrase retrieval succeeded; the daily shop returned four real items. These describe observed samples rather than data every account is guaranteed to receive.

After group-control deployment, checks confirmed plugin activation, early-entry and segmented-send guards, forward-hook registration and QQ online status. Limited recent history contained no actual nested card for an end-to-end check: **complete reading of the user's nested record remains unverified**. Images in forwards are only marked as present, not visually interpreted. Final ordinary segmentation on a phone still needs normal-use verification.

Earlier checks confirmed the recovery manager online, the independent guard healthy, supervised restart after manager exit and missing-service repair. Recent stability is user feedback, not an uptime guarantee. This update did not restart QQ, reinstall recovery or deliberately cause a disconnect.

## Untested operations and publication checks

Publication testing sent no actual Bilibili root/nested/image comments, dynamics or QQ alerts, arbitrarily liked/saved no videos, performed no purchases or recharges, read no Bilibili private messages, triggered no Tencent verification and tested no full-device reboot. Actual public visibility, alert delivery and the first normal write cannot be proven by offline tests or a single online flag.

No real configuration, account bindings, subscriptions, cookies/tokens, match records, conversations, memories, pending drafts, letters, databases, image libraries or logs are published. AGPL attribution is retained, and only public knowledge data is included. New capabilities are disabled in the sharing configuration. AstrBot4.29.1 is the reference version; other versions still require checks of internal pipelines and OneBot integration.

The owner-role timing fix was additionally checked on the device with real framework events and the real waking-stage entry, using an inert sender. All nine assertions passed without real QQ sends. This is a pipeline simulation, not a claim that the user has confirmed the command on the phone.
