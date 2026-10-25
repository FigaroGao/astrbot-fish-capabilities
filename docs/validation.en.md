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
