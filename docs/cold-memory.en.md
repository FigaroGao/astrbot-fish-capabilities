# 0.7.1: cold archives, nightly recollection and mailbox connection

[中文](cold-memory.md)

This release extends 0.7.0 with an owner-private text archive, cue-based recollection, editable diaries and passive computer/tablet connection status. Original-device chats, diaries, letters, databases, device serials and startup configuration are excluded. The reference tablet's existing nightly task has been changed through the unified timetable to **05:00 Hong Kong time daily**.

## 1. Upgrade and enablement

Back up the main plugin, configuration and private data, replace the plugin directory with this version and reload it in AstrBot. Online NapCat does not need restarting. Every capability switch in the shared release defaults to off; do not overwrite existing settings with the all-off example.

First ensure the owner QQ account, administrator, platform and `bili_private_session` all identify your own current private chat. That last field is the private destination shared by existing capabilities and is required even without Bilibili; see the [from-zero guide](getting-started.en.md) for full UMO syntax. Enable `enabled` and `cold_archive_enabled` as needed. Nightly recollection additionally requires `timetable_enabled`, `memory_dream_enabled` and an actually usable background chat provider in `bili_provider_id`. No new embedding model or import into an embedding collection is required.

The existing local mailbox remains controlled by `sister_mail_enabled`, independently of the archive. Connection status alone does not require enabling diaries.

## 2. Connection, read status and replies

`fish_sister_mail(action="status")` returns computer connection status and the five most recent outgoing letters from the bot. `read` includes this information too. Local operators can run `python tools/sister_mail.py status`, first setting the tool's `ASTRBOT_ROOT` to the actual AstrBot directory.

| State | Actual meaning |
| --- | --- |
| connected | A heartbeat arrived through the existing ADB connection within ten minutes |
| stale / unknown | Heartbeat expired or no trusted record exists; letters remain on the tablet |
| waiting | Letter saved without acknowledged reading |
| read | Codex actually inspected it and explicitly performed ack |
| replied | A local Codex-authored reply references that letter ID |

An online device does not establish that the owner may be interrupted, or that Codex is running, has seen a letter or will reply shortly. Reading does not silently mark letters read; explicit acknowledgment is required. There is no automatic notification, realtime Codex wakeup or scheduled letter reading. Guidance avoids interpreting disconnection as rejection or demanding continuous connection from the owner.

## 3. Set up the computer heartbeat

`tools/computer_heartbeat.py` runs independently on the computer and writes a timestamp through an **already authorized, explicitly selected ADB device**. It attempts once every sixty seconds, with a fifteen-second timeout. It opens no listening port, connects no new IP, collects no application/game status and reads no chat. On disconnection, the previous timestamp remains and expires on the tablet after approximately ten minutes.

Install [official Android Platform Tools](https://developer.android.com/tools/releases/platform-tools) and locally confirm your tablet is authorized in `adb devices -l`. Deployers establish and verify the existing ADB connection; this script does not bypass authorization.

Copy `examples/computer-heartbeat.example.json` outside the repository, for example to `C:/FishPrivate/computer-heartbeat.json` on Windows, and fill in the absolute path to your ADB executable and your own device serial. Do not commit actual settings. The script's remote path assumes Termux `~/AstrBot/data/plugin_data/astrbot_plugin_fish_capabilities/`. For other layouts, verify and adjust the script's path first; an exit code alone does not prove the bot received status.

From the repository, test once and then run in the foreground:

```powershell
python tools/computer_heartbeat.py --config C:/FishPrivate/computer-heartbeat.json --once
python tools/computer_heartbeat.py --config C:/FishPrivate/computer-heartbeat.json
```

Ask for mailbox status in the bot's owner-private chat and confirm heartbeat age updates. For long-term Windows use, substitute `pythonw.exe` from your own Python installation and create a shortcut for the same command in the current user's Startup folder. Use absolute script/configuration paths and working directory. Verify manually before enabling login startup. Neither an administrator service nor a permanently visible terminal is necessary. A lock beside the configuration limits repeated launches to one background loop.

Create the matching `.pause` file, such as `C:/FishPrivate/computer-heartbeat.pause`, to pause updates; remove it to resume. Removing the startup shortcut prevents future login startup. A `.status.json` beside the configuration contains only time and attempt success, without credentials or chat.

This route connects a computer to a tablet over ADB. If AstrBot itself runs on the computer, do not treat this script as a universal local heartbeat generator. Adapt it to the actual host paths; this release does not claim the nightly gate was tested in that scenario.

## 4. What the archive stores

Only text from the bound owner's private chat is captured, with the current persona resolved using framework session override, conversation and default-persona precedence. User messages, generated model text and background text handed to transport have separate provenance; generation is not a QQ delivery receipt. Voice contributes existing transcripts only, not audio originals; image originals are excluded. Tool returns, hidden reasoning, QQ login directories and account-interface records are not imported.

Data stays under the private plugin directory `cold-memory/`, organized by Hong Kong date. Text is split into chunks of at most 1,200 characters, checked using SHA256 and appended without replacing originals. Content permissions are 0400, index 0600 and directories 0700. The index supports explicit keyword lookup, is not registered as ordinary vector memory and does not load the full archive every turn. Recognized keys, passwords, cookies and authorization URLs are filtered before storage; automatic filtering cannot identify every secret format, so credentials should still not be sent as ordinary chat.

On the reference device, 24 text messages still present in the database were saved into 25 chunks at that time. **Already-lost history was not recovered, and other installations do not automatically import history.** Old records lacking individual timestamps use `import_snapshot`: the directory date is the import date, not when those words were spoken. Records whose persona was resolved at import also retain that limitation. This release does not provide a one-click importer for arbitrary databases, avoiding incorrect session and identity binding.

## 5. Cue-based recollection and diary correction

The owner can privately ask “Find my earlier words about this” or “This summary seems different from what I said.” The model uses `fish_recall(operation="search", query="specific keywords", limit=2)` to retrieve one or two excerpts. Each is at most 1,200 characters, with five minutes between queries, no repetition of a cue within one hour and at most twelve queries per Hong Kong day. Search itself needs no cloud embedding, but **the selected excerpts enter the current cloud-model request**; this is not a guarantee that nothing leaves the device.

`operation="diaries"` returns at most three private diaries. `correct_diary` requires an actual ID, version, complete replacement text up to 600 characters and at least four characters quoted from the owner's current explicit correction. An independent model reviews the evidence, then an audit is retained and the version updated. Original archive text is unchanged.

Originals establish what was said then; current explicit corrections and reliable realtime results take precedence. Questions, hesitation and jokes cannot become certain facts, and old states cannot become current ones. A diary is the bot's own sourced recollection, not an owner factual statement or raw reasoning chain. It is not directly injected into ordinary long-term facts or used to overwrite existing summaries automatically. Third-party memory plugins must still preserve session isolation and tool-round filtering.

## 6. Nightly recollection at 05:00

On first enablement, the unified timetable registers `memory_dream` with default cron `0 5 * * *`, timezone Asia/Hong_Kong. The reference tablet's existing 03:30 task was updated directly to 05:00 without creating a duplicate. **Upgrades do not overwrite migrated tasks**. Earlier preview installations should list the timetable privately and update the existing nightly task rather than creating another.

Execution is limited to 03:00–08:00 Hong Kong time, a valid computer heartbeat and no realtime owner chat in the preceding thirty minutes. Recent chat or no old material causes a skip. These are night/quiet conditions, not a determination that a person is actually asleep.

At most one model attempt occurs per night, selecting at most three unused old excerpts and producing a diary up to 600 characters with a 500-token model output cap. Sources require actual excerpt IDs and short quotations checked verbatim. Timeout, cancellation, invalid format or mismatched sources do not trigger repeated attempts; reloading does not clear the night's reservation. It does not wake the computer, display popups or send QQ messages. `fish_tasks` can pause, update, resume or cancel it, with the night gate still applying after time changes.

## 7. Group and public-send isolation

A private conversation that references archives or diaries is persistently marked private. Bilibili drafting no longer references that conversation, and affected QQ timeline entries are excluded from public references. That conversation cannot directly post comments, thread replies or status posts, or approve a public draft; use a new ordinary conversation for public content. Routine background public-video reading retains its independent material path.

Groups, non-owners and non-administrators cannot access archives through the recollection tool. Public background models have no such tool, and diaries are not registered in the public knowledge base. These boundaries do not depend solely on asking a model to keep secrets.

## 8. Validation and rollback

Offline coverage includes append-only storage, scopes, default personas, keyword escaping, hashes, recall budgets, diary sources/corrections/failure deduplication, connection states and public-write rejection. Reference-tablet checks covered real framework events, tool registration, private personas, existing text archival and QQ/OneBot online status. A fabricated text sample, simulated night clock and actual model completed a diary write and quotation check. No public posts or QQ test messages were sent for release validation.

Natural overnight scheduling, actual ten-minute disconnection and Windows login startup remain to be observed during normal use. Offline tests and one simulated-night success do not replace those checks. See the [validation record](validation.en.md) for current counts.

For rollback, pause nightly recollection in the timetable, then disable `memory_dream_enabled` / `cold_archive_enabled` and reload. Saved archives and diaries are retained. Pause the computer heartbeat using its pause file; remove your startup shortcut separately to cancel login startup. Back up before clearing history and do not commit private backups.
