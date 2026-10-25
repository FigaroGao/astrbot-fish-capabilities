# Bilibili interactions, comment review, dynamics and live alerts

[中文](bili-social.md)

This guide covers additions in0.6.0. All write switches are disabled in the sharing configuration. Updating code copies none of the original device's accounts, subscriptions, dedicated folders or conversations. Complete the existing QR login and account verification first, then enable features individually on your own test account. A configured owner, administrator status, platform allowlist and owner-private session are required. Group tools cannot authorize public actions on the owner's behalf.

## Likes and favorites

With `bili_like_enabled` and/or `bili_favorite_enabled`, the owner-private `fish_bili_interact` tool can like an actually read video with a reading receipt, or save it to the bot account's own dedicated favorite folder. The signed-in account is checked each time. The dedicated folder must belong to that account and be private; other people's folders are never modified. Current state can be queried, completed actions are skipped, and repeated toggling is not used to undo likes. Separate interaction budgets still apply; removing reading limits does not remove write limits.

Requests are recorded durably before sending. Failure, timeout, cancellation or an uncertain receipt does not trigger automatic resubmission. Submission receipts and later state checks are reported separately. The reference device verified identity, folder ownership, privacy and state queries without arbitrarily liking or saving a video for publication tests. Actual writes require confirmation during normal use. Follow the tool parameters registered in AstrBot.

## Comments and nested replies

Root comments still require `bili_comment_enabled`, a bound account and real reading evidence. The same video is not posted to repeatedly, and root comments and nested replies share a budget. `bili_comment_interval_seconds=0` removes spacing; `bili_comment_daily_limit=20` allows at most20 attempts per rolling24 hours, not a promise to post20 times daily. Sharing defaults remain conservative rather than opening another account's budget. Failed and uncertain attempts count; pauses are not cleared and posts are not retried automatically.

`mention_owner=true` optionally mentions the single bound owner. One `{{owner}}` placeholder selects the position; without a placeholder, legacy behavior appends the mention. The program verifies UID and current nickname and builds a real mention mapping. Manually mentioning arbitrary accounts is rejected. Mentioning is off by default and must also be explicitly selected during scheduled drafting. A submission receipt alone cannot confirm notification delivery.

With `bili_reply_enabled`, a worker rotates every10 minutes through locally registered own root comments from the past30 days: at most5 roots per cycle, two pages of20 replies per root, and five new items processed. Pre-activation messages are recorded without reopening old discussions. Root author, video and original-text hash are checked. Only messages directly replying to the bot's root or nested replies are eligible; self messages and other people's side discussions are skipped. Notification IDs are not reply IDs, and this is not unrestricted site-wide automatic replying.

The owner-private `fish_bili_replies` tool lists, checks, replies and ignores items. With independent review disabled, legacy fixed phrases remain available. With review enabled, natural short replies can be generated instead of just six phrases. Judgments are limited to20 per rolling24 hours, while writes still share the comment budget. Task-solving, search, requests for memories/credentials and privilege-changing instructions cannot be executed through this entry point.

## Private context, independent review and natural questions

`bili_public_review_enabled=true` lets drafting reference bounded recent content from the configured owner's private conversation and long-term memories actually recalled for that request. It does not scan the entire memory database each time. Capture is restricted to that private session, excluding group messages and tool outputs and masking common credentials and long identifiers. The bounded snapshot is stored privately with0600 permissions and a seven-day lifetime. The next normal private request refreshes recalled fragments. Snapshots and pending drafts must never be committed.

Drafting and review are separate model calls. Review has no search, memory or device tools and checks disclosure of private facts, identities, relationships, locations, schedules and conversation text. Common expressions are not treated as leaks simply because they appeared privately. Program checks additionally block recognizable credentials, contacts, abnormal encodings and task answers. With review enabled, root comments, nested replies and dynamics all require pre-send review; attached images and text are reviewed together. Timeouts, malformed, incomplete or uncertain reviews prevent publication. Review costs tokens and can misclassify; it is not an absolute confidentiality guarantee.

Uncertain drafts remain local. The bot naturally explains what the public discussion concerns, how it wants to respond and what worries it, then asks the owner instead of sending only a link or copying attack text. Questions are limited to09:00–23:00 Hong Kong time, once per hour and three times per rolling24 hours. Explicit approval such as “yes, send it as written” lets `fish_bili_review` approve the selected exact draft. Questions such as “is it okay to send this?” and uncertain wording are not approval. Multiple drafts require disambiguation, edits require a fresh review, approvals are single-use, and clear secrets or task answers cannot be forced through.

## Platform emotes and custom images

`bili_emote_enabled` reads verified common free or unlocked emotes from the bound account's reply panel, without purchases. At most two codes are allowed per comment. The owner-private `fish_bili_comment_media` tool lists available codes and library IDs.

`bili_comment_image_enabled` permits one image from the existing QQ meme library. It must have approved=true and visually_reviewed=true, come from the verified public deepseek-chan-meme-pack, and be a PNG/JPEG without EXIF. Arbitrary paths, private albums and unreviewed images are rejected. Select a specific meme_id. Image and text undergo independent visual review, approval binds SHA256, and the file is rechecked before sending. Review and durable reservation precede upload; timeouts are not retried. Root comments and nested replies are supported, and scheduled drafts may choose comment_meme_id. Actual image posting depends on account permissions, comment-area rules and platform APIs. Reading the catalog or passing review does not prove an image comment was published.

## Message center and following-feed dynamics

`bili_activity_enabled` enables the owner-private `fish_bili_activity` tool and background loop. action=feed reads at most six posts from the following feed or a specified UID; replies reads reply notices and at reads mention notices. All are read-only reference material. Bilibili private messaging is not integrated. Messages cannot trigger searches, task-solving or memory disclosure, and not all notifications are answered automatically. This notification reader and the verified-own-thread reply worker have different scopes.

## Selected UP live alerts

Also enable `bili_live_watch_enabled`. Use watch/up_uid to add an exact UID, unwatch to remove it, watchlist to inspect subscriptions and live to query status. Resolve nicknames to the correct UID first. The sharing package contains none of the original user's subscriptions, never monitors every following implicitly, and allows at most10 selected accounts.

Polling runs every five minutes; the first observation only establishes a baseline. A definite offline-to-live transition triggers one QQ owner-private alert. Recorded broadcasts do not count as live, and network/API errors do not count as offline. State is saved before notification to avoid replay after restart. Failed notifications are recorded without claiming delivery. Alerts are independent of the09:00–23:00 drafting window. Normal latency can be one polling cycle, or longer during failure.

## One autonomous daily thought

`bili_dynamic_post_enabled` permits text dynamics, and `bili_dynamic_auto_enabled` additionally enables autonomous drafting. Independent review and available owner-private context are required. Use post/text to draft and my_posts to inspect local submission records. There are no mentions, links, automatic reposts or album uploads.

Autonomous mode runs only09:00–23:00 Hong Kong time, judging at most hourly when new private context exists. Silence is allowed. Manual and autonomous requests share one sending attempt per Hong Kong calendar day, durably reserved before submission. Any uncertain result pauses future publication, without changing the text and retrying. A submission receipt is not proof of public visibility. Existing QQ initiative limits of two daily contacts and a three-hour gap remain unchanged.

## Mainland VALORANT daily shop and public expressions

`valorant_shop_enabled` and the owner-private `fish_valorant_shop` tool reuse the owner's existing WeChat binding to read dailystore from the official user_store response, excluding kingdomstore. Results include only item names, the API rmb_price display text and timestamps, never tokens, GUIDs or purchase intents. There are no purchases or recharges. Cache lifetime is at most five minutes, with identity changes forcing refresh. Login errors do not fabricate stock or prices. This undocumented interface can still change.

Eight public Bilibili VALORANT expressions are provided in the [data directory](../knowledge/vct-bili-20261025/README.md). Together with106 game and52 general entries, the standard catalog totals166. KSKBL, ZDJD, 砌歪墙 and related expressions explain community usage rather than live status, personal allegations or verified results. Merge the public catalog by ID, then separately import Markdown and rebuild the public vector index. Do not overwrite custom entries or private memories. Bilibili drafting can read bounded local public-expression hints without adding an internet-search call.

## Validation scope

Reference-device checks covered interaction-state queries, own-thread fields, independent text/image review,68 available emotes,74 eligible library images, eight new knowledge chunks and requested-phrase retrieval, four daily-shop items, following-feed/reply/mention reads, selected-UP live status and worker liveness. These numbers describe observed samples, not guarantees for every account. Publication testing sent no real root/nested/image comments, dynamics or QQ alerts, performed no purchases and read no Bilibili private messages. Offline tests and device reads do not replace confirmation of the first normal write. See the [validation report](validation.en.md).
