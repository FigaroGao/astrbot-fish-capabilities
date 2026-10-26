# Deploying with DSH or a similar assistant

[中文](assistant-deployment.md)

DSH or another coding assistant helps inspect and configure the installation; it does not replace AstrBot as the plugin runtime. Copying this repository into another framework does not establish compatibility. Copy the following prompt and fill in device information, without passwords, keys or cookies.

```text
Help me deploy https://github.com/FigaroGao/astrbot-fish-capabilities from zero.
Device: [OS, CPU architecture, memory, existing Termux/Ubuntu/Python].
Read the repository README, docs/getting-started.en.md, docs/release-0.7.0.en.md,
docs/privacy.en.md and validation guide, then inspect my actual environment and versions.
Back up existing configuration first; avoid overwriting an online QQ setup or starting a second NapCat.
Stage one: QQ text chat using NapCat+AstrBot only. Stage two: install only the main plugin and test Hong Kong weather.
Then configure authorization scopes individually before timetable, Bilibili, cloud memory and optional speech recognition.
Label every command as native Termux, Ubuntu or computer terminal and use actual paths.
Do not copy author identities, private configuration or memories, or install the repository root as one plugin.
When credentials are needed, let me enter them in a trusted local interface, not in chat or Git.
Report actual gaps on GCP patch mismatch, missing LivingMemory interfaces or native dependency failure; do not claim completion.
Keep public comments, status posts and account writes off until I explicitly enable them.
Finish with actual actions, successful checks, untested items, rollback and routine startup commands.
```

## Acceptance checks

Ask the assistant for actual installation directories, Python paths, versions, service management and enabled switches, without real credentials. Verify QQ delivery, successful weather calls, group-scope isolation and task listing/pause behavior individually. Redact screenshots and logs. Do not upload configuration backups or login data.

For a partial migration, explicitly request “weather and timetable only; everything else off.” A model discussing a capability does not establish an interface exists. Have the assistant rely on source code and receipts rather than inventing configuration from another bot's recollections.
