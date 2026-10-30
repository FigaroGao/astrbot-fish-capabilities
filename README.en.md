# Fish capabilities for AstrBot

[中文](README.md) | [English — full translation](README.en.md)

Latest: [October 30–31 scene-based video detail selection, context costs, slow-task acknowledgements, Lecture timetables and Vocu integration](docs/update-20261031.en.md). Desktop chat, isolated watch memory, action receipts, the new UI and the voice switch live in the separate [Xiaojing-Screenmate](https://github.com/FigaroGao/Xiaojing-Screenmate) repository and are not bundled into this plugin installer.

Latest: [October 29 course notebook, Canvas integration, brief match review and other fixes](docs/update-20261029.en.md), including local binding, configuration and actual validation limits.

Latest fixes: [2026-10-28 changes, configuration and validation](docs/update-20261028.en.md). Includes video/dynamic repairs, sleep boundaries, six character references and comment-emote style; every item is fully translated from Chinese.

Adds intent-based conversation, Bilibili reading and interaction, weather, game records, memes, memory integration and a unified timetable to AstrBot + NapCat. Includes ARM64 Android tablet and computer deployment routes. Share release **0.8.0 · 2026-10-27**.


Version 0.8.0 adds twenty companionship/management improvements, read-only tone diagnostics, batched group conversation, private meme opportunities, selective video/page reading/character references, comment media candidates, and public Codex announcements. See the [complete update and migration guide](docs/release-0.8.0.en.md) and [actual deployment and untested limits](docs/deployment-20261027.en.md). All shared feature switches remain disabled by default.

This is a configurable trial release, not a bundle containing an existing account. All capability switches default to off; owner identities and authorized scopes are empty. Repository maintainer credits do not configure the bot's owner. No private conversations, memories, persona prompts or login sessions are distributed.


Release 0.7.1 adds [cold-archive recollection, 05:00 nightly review and mailbox connection status](docs/cold-memory.en.md). Only generic implementation is shared, disabled by default, without private archives or device bindings.

## Start here

1. [From-zero deployment: tablet and computer](docs/getting-started.en.md): establish QQ text replies before enabling capabilities individually.
2. [Deployment with DSH or a similar assistant](docs/assistant-deployment.en.md): copyable deployment prompts and acceptance checks.
3. [0.7.0 features, configuration and migration](docs/release-0.7.0.en.md): start here for an existing installation.
4. [Privacy and identity configuration](docs/privacy.en.md), [validation scope](docs/validation.en.md).

## Capabilities and boundaries

| Capability | Behavior and requirements |
| --- | --- |
| Private archive and recollection | Append-only local text, bounded cue-based quotations and editable sourced diaries; current explicit corrections take precedence |
| Mailbox connection | Device heartbeats are separate from actual reading and replies; no automatic Codex wakeup |
| Unified timetable | The owner can use natural language in private chat through `fish_tasks` to create, update, pause, resume or cancel tasks; reminders, weather, shop, browsing and checks reuse one scheduler |
| Cross-window timeline | Stores bounded QQ and Bilibili activity summaries for owner-private retrieval; historical events are not current states and are not automatically disclosed to groups |
| Memory retrieval and correction | `fish_memory_edit` searches old memories in the current scope, independently reviews corrections, checks versions and keeps an audit; requires compatible LivingMemory interfaces |
| Bilibili reading | Search, the bot account's personalized homepage, candidate selection, subtitles and sampled frames, comments and notes; no deep reading beyond ten minutes, and sampling is not complete viewing |
| Bilibili interaction | Separate switches and review for comments, thread replies, likes, favorites, native emotes and approved image assets, followed-account activity, selected streamer alerts and at most one daily status post |
| Owner mentions on Bilibili | Verifies sender, recipient account and video target before reading the video and comments and optionally replying; does not replay old notices or repeat writes with unknown outcomes |
| Group intent and quiet mode | Identifies conversation targets and combines backlog; owner `/闭嘴` or an intent decision pauses the current group for 120 seconds; GCP integration requires checking the patch baseline |
| Everyday capabilities | Hong Kong weather, private queries of authorized group records, bounded nested forwards, mainland Valorant WeChat records and daily shop, categorized memes and a public knowledge base |
| Speech recognition | Reuses an Alibaba provider key with four Paraformer routes, local quota reservations and a short-lived cache; this is not TTS and does not automatically send voice replies |
| Context and expression | Bounded history, rolling summaries, compact tool output and ordinary text segmentation; appends companionship guidance without replacing the main persona |
| QQ recovery | Independent Termux recovery manager and watchdog, preferring built-in recovery, bounded quick login and optional password fallback; stops retries for manual verification |

Not every reference-device customization is included: the complete LivingMemory two-layer group-memory changes have not been packaged into a portable patch, and the GCP patch is not a universal installer for any upstream version. See [memory](docs/memory.en.md) and [intent integration](docs/intent.en.md). Arena Breakout PC records, Azure/Vocu voice tuning and local GPU speech are not completed capabilities.

## Layout and installation principles

The main plugin is `astrbot_plugin_fish_capabilities/`; copy it into the actual AstrBot `data/plugins/` directory. This repository also includes tools, a recovery manager and patches: **do not install the repository root as one AstrBot plugin**. Install dependencies into the Python environment that actually runs AstrBot. Reference framework versions are AstrBot 4.29.1 and NapCat 4.18.38; check compatibility for other versions.

`examples/config.disabled.json` is an all-off template, not a working private configuration. Bilibili, Valorant, speech and public writes require separate enablement; the master switch does not grant account permissions.

## Other guides

[QQ recovery](docs/recovery.en.md) · [Group controls](docs/group-controls.en.md) · [Bilibili interaction](docs/bili-social.en.md) · [Existing capability configuration](docs/new-capabilities.en.md) · [Memory freshness](docs/memory-policy.en.md) · [Memes](docs/memes.en.md). For fixed times and old limits in earlier guides, use the 0.7.0 migration guide and actual local configuration instead.

## Tests and sources

```bash
python -m pip install -e '.[test]'
python -m pytest -q tests
python -m unittest discover -s recovery -p 'test_*.py'
```

Isolated tests do not replace real-account end-to-end validation. See the [validation record](docs/validation.en.md) for pass counts, device checks and untested cases. Neither HarmonyOS background survival nor unofficial QQ access can be guaranteed permanently stable.

Code is released under [AGPL-3.0](LICENSE); see [NOTICE](NOTICE.md) for third-party sources and asset boundaries. Initiated, deployed and maintained by FigaroGao, with Codex (OpenAI) assisting design, implementation, tests and documentation. Commits retain Codex coauthor credit; this does not imply official OpenAI endorsement.
