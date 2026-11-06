# Capability catalog and installation routes

[中文](capabilities.md) | [English](capabilities.en.md)

Names such as fish-val and fish-bili are navigation labels, not separate plugin packages. Most capabilities share astrbot_plugin_fish_capabilities and its Brain Core. Download the common source once, install the main plugin, then enable only the capabilities you need. Recovery and Screenmate have separate installation routes.

[Download common source ZIP](https://github.com/FigaroGao/astrbot-fish-capabilities/archive/refs/heads/main.zip) · [Install from scratch](getting-started.en.md) · [Architecture](architecture.en.md)

| Entry | Capability | What it does | Setup | Source |
|---|---|---|---|---|
| [fish-brain](#fish-brain) | Shared core | Attention, working state, preemption and persona context | [Guide](brain-core.en.md) | [Source](../astrbot_plugin_fish_capabilities/services/brain.py) |
| [fish-chat](#fish-chat) | Chat and participation | Group intent, silence, backlog merging and segmentation | [Guide](intent.en.md) | [Source](../astrbot_plugin_fish_capabilities/services/intent_runtime.py) |
| [fish-memory](#fish-memory) | Memory and timeline | Long-term integration, archives, corrections and activity indexes | [Guide](memory.en.md) | [Source](../astrbot_plugin_fish_capabilities/services/memory_editor.py) |
| [fish-bili](#fish-bili) | Bilibili | Selection, video understanding, topics, comments and dynamics | [Guide](bili-social.en.md) | [Source](../astrbot_plugin_fish_capabilities/services/bilibili.py) |
| [fish-val](#fish-val) | Mainland VALORANT | WeChat binding, records, incremental sync and daily shop | [Guide](new-capabilities.en.md) | [Source](../astrbot_plugin_fish_capabilities/services/valorant.py) |
| [fish-canvas](#fish-canvas) | Courses and Canvas | School courses, assignments, announcements and personal progress | [Guide](update-20261029.en.md) | [Source](../astrbot_plugin_fish_capabilities/services/course_context.py) |
| [fish-tasks](#fish-tasks) | Unified schedule | Natural-language reminders, browsing and maintenance schedules | [Guide](release-0.7.0.en.md) | [Source](../astrbot_plugin_fish_capabilities/services/timetable.py) |
| [fish-meme](#fish-meme) | Memes and expression | Categorized library, sending opportunities, style references and diagnostics | [Guide](memes.en.md) | [Source](../astrbot_plugin_fish_capabilities/services/tone_diagnostics.py) |
| [fish-weather](#fish-weather) | Weather and daily tools | configured-city weather and authorized group-record queries | [Guide](getting-started.en.md) | [Source](../astrbot_plugin_fish_capabilities/services/weather.py) |
| [fish-speech](#fish-speech) | Speech | Speech recognition and optional TTS adapters | [Guide](update-20261031.en.md) | [Source](../astrbot_plugin_fish_capabilities/services/asr.py) |
| [fish-mail](#fish-mail) | Mailbox | Local letters, replies, read receipts and connection status | [Guide](cold-memory.en.md) | [Source](../astrbot_plugin_fish_capabilities/services/sister_mail.py) |
| [fish-recovery](#fish-recovery) | QQ recovery | Separate recovery manager, bounded relogin and verification stop | [Guide](recovery.en.md) | [Source](../recovery/) |

<a id="fish-brain"></a>

## fish-brain · Shared core

Attention, working state, preemption and persona context.

[0.9.2 behavior adjustment and read-only checks](self-regulation.en.md): fixed allowlist, 24-hour expiry, revisions/audit and issue letters; no source or permission changes.

[Download](https://github.com/FigaroGao/astrbot-fish-capabilities/archive/refs/heads/main.zip) → [Main plugin](../astrbot_plugin_fish_capabilities/) → [Setup guide](brain-core.en.md)

<a id="fish-chat"></a>

## fish-chat · Chat and participation

Group intent, silence, backlog merging and segmentation.

[Download](https://github.com/FigaroGao/astrbot-fish-capabilities/archive/refs/heads/main.zip) → [Main plugin](../astrbot_plugin_fish_capabilities/) → [Setup guide](intent.en.md)

<a id="fish-memory"></a>

## fish-memory · Memory and timeline

Long-term integration, archives, corrections and activity indexes.

[Download](https://github.com/FigaroGao/astrbot-fish-capabilities/archive/refs/heads/main.zip) → [Main plugin](../astrbot_plugin_fish_capabilities/) → [Setup guide](memory.en.md)

<a id="fish-bili"></a>

## fish-bili · Bilibili

Selection, video understanding, topics, comments and dynamics.

0.9.1 adds segmented danmaku, parts/tags/comments, own-account history and folders, watch later, follows, reposts and approved-library image dynamics: [expansion guide](bili-valorant-expansion.en.md).

[Download](https://github.com/FigaroGao/astrbot-fish-capabilities/archive/refs/heads/main.zip) → [Main plugin](../astrbot_plugin_fish_capabilities/) → [Setup guide](bili-social.en.md)

[Local utility](../tools/bili_login.py) runs inside the documented environment. Set ASTRBOT_ROOT to your actual installation first. Local shortcuts such as fish-val-login are not automatically installed by cloning this repository.

<a id="fish-val"></a>

## fish-val · Mainland VALORANT

WeChat binding, records, incremental sync and daily shop.

0.9.1 adds map/agent/trend/weapon/teammate analytics, local history and shop wishlists: [expansion guide](bili-valorant-expansion.en.md).

[Download](https://github.com/FigaroGao/astrbot-fish-capabilities/archive/refs/heads/main.zip) → [Main plugin](../astrbot_plugin_fish_capabilities/) → [Setup guide](new-capabilities.en.md)

[Local utility](../tools/valorant_wechat_login.py) runs inside the documented environment. Set ASTRBOT_ROOT to your actual installation first. Local shortcuts such as fish-val-login are not automatically installed by cloning this repository.

<a id="fish-canvas"></a>

## fish-canvas · Courses and Canvas

School courses, assignments, announcements and personal progress.

[Download](https://github.com/FigaroGao/astrbot-fish-capabilities/archive/refs/heads/main.zip) → [Main plugin](../astrbot_plugin_fish_capabilities/) → [Setup guide](update-20261029.en.md)

[Local utility](../tools/canvas_login.py) runs inside the documented environment. Set ASTRBOT_ROOT to your actual installation first. Local shortcuts such as fish-val-login are not automatically installed by cloning this repository.

<a id="fish-tasks"></a>

## fish-tasks · Unified schedule

Natural-language reminders, browsing and maintenance schedules.

[Download](https://github.com/FigaroGao/astrbot-fish-capabilities/archive/refs/heads/main.zip) → [Main plugin](../astrbot_plugin_fish_capabilities/) → [Setup guide](release-0.7.0.en.md)

<a id="fish-meme"></a>

## fish-meme · Memes and expression

Categorized library, sending opportunities, style references and diagnostics.

[Download](https://github.com/FigaroGao/astrbot-fish-capabilities/archive/refs/heads/main.zip) → [Main plugin](../astrbot_plugin_fish_capabilities/) → [Setup guide](memes.en.md)

<a id="fish-weather"></a>

## fish-weather · Weather and daily tools

configured-city weather and authorized group-record queries.

[Download](https://github.com/FigaroGao/astrbot-fish-capabilities/archive/refs/heads/main.zip) → [Main plugin](../astrbot_plugin_fish_capabilities/) → [Setup guide](getting-started.en.md)

<a id="fish-speech"></a>

## fish-speech · Speech

Speech recognition and optional TTS adapters.

[Download](https://github.com/FigaroGao/astrbot-fish-capabilities/archive/refs/heads/main.zip) → [Main plugin](../astrbot_plugin_fish_capabilities/) → [Setup guide](update-20261031.en.md)

<a id="fish-mail"></a>

## fish-mail · Mailbox

Local letters, replies, read receipts and connection status.

[Download](https://github.com/FigaroGao/astrbot-fish-capabilities/archive/refs/heads/main.zip) → [Main plugin](../astrbot_plugin_fish_capabilities/) → [Setup guide](cold-memory.en.md)

[Local utility](../tools/sister_mail.py) runs inside the documented environment. Set ASTRBOT_ROOT to your actual installation first. Local shortcuts such as fish-val-login are not automatically installed by cloning this repository.

<a id="fish-recovery"></a>

## fish-recovery · QQ recovery

Separate recovery manager, bounded relogin and verification stop.

[Recovery source](../recovery/) and [host guard](../astrbot_plugin_fish_host_guard/) are installed separately according to the recovery guide; they are not enabled by installing the main plugin.

## Desktop companion

[Download and setup: Xiaojing-Screenmate](https://github.com/FigaroGao/Xiaojing-Screenmate). This separate desktop component is not included in the capability plugin.

