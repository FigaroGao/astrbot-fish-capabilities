# From-zero deployment: tablet or computer

[中文](getting-started.md)

The goal is to establish ordinary text chat with your own test QQ account before installing this repository's capabilities. A local language model is unnecessary: chat, vision and embedding can use cloud APIs. This tutorial was not reinstalled and tested on every device type. The reference device is an ARM64 Android tablet/HarmonyOS 4.2 running Termux + Ubuntu proot; compatibility with every HarmonyOS version must not be assumed.

## 1. Preparation and routes

Prepare a test QQ account, stable networking, sufficient storage and your own chat API. Embedding and vision are separate capabilities; basic text chat does not require buying embedding service first. Enter keys only in local management pages. Unofficial QQ access may require QR login, identity verification or trigger account restrictions.

| Host | Recommended route | Notes |
| --- | --- | --- |
| ARM64 Android tablet | Manage from Termux; run AstrBot in Ubuntu proot and use NapCat's official Termux route | Native Termux uses Bionic, so desktop Linux wheels may not work; install Python dependencies inside Ubuntu |
| Windows computer | Python 3.12 + uv running AstrBot source, with official NapCat Windows package | Closing terminals or sleeping the computer affects service; the Termux recovery installer does not install directly on Windows |
| Linux computer | Python 3.12 + uv source deployment and official NapCat Linux installer | Select packages for the actual architecture and manage persistence on the host |

APK bundles are an alternative to investigate, but their support claims are not tests performed by this tutorial. Do not install several bundles simultaneously. Avoid Docker initially to simplify networking: its 127.0.0.1 is not the host or another container.

## 2A. Tablet: Termux and AstrBot

Choose a trusted source from the [official Termux installation instructions](https://github.com/termux/termux-app#installation), keeping companion apps from the same signing source. Run these in **native Termux**, checking each result:

```bash
pkg update
pkg upgrade
pkg install git curl termux-tools proot-distro
termux-wake-lock
git clone https://github.com/fii6/astrbot_termux.git
cd astrbot_termux
```

Inspect the downloaded script before executing it. Do not repeat a completed installation:

```bash
bash ./astrbot_termux.sh
astr
```

This [upstream route](https://github.com/fii6/astrbot_termux) provides `astr` to start AstrBot and `astr shell` to enter its Ubuntu environment. Installation may be slow; retain the final error on failure instead of repeatedly pasting Ubuntu commands into native Termux. Identify the actual AstrBot directory and Python environment; install later dependencies there. If a script version changes paths, follow its actual output.

## 2B. Computer: AstrBot source

Install Python 3.12, Git and [uv](https://docs.astral.sh/uv/getting-started/installation/). These commands work in PowerShell or a Linux terminal, starting in a working directory you choose:

```bash
git clone --branch v4.29.1 https://github.com/AstrBotDevs/AstrBot.git
cd AstrBot
uv sync --python 3.12
uv run --no-sync main.py
```

The pinned version reproduces the plugin's reference environment; it does not mean never upgrading. Back up and check compatibility before upgrades. See [AstrBot's source deployment guide](https://docs.astrbot.app/deploy/astrbot/cli.html). After adding plugin dependencies, continue using `--no-sync` so environment synchronization does not remove extras.

## 3. Start NapCat and log into QQ

Open **another native Termux session on the tablet**, download and inspect the [official Termux installer](https://github.com/NapNeko/NapCat-Installer):

```bash
cd ~
curl -fL -o napcat.termux.sh https://raw.githubusercontent.com/NapNeko/NapCat-Installer/main/script/install.termux.sh
bash napcat.termux.sh
proot-distro login napcat -- bash -c 'xvfb-run -a /root/Napcat/opt/QQ/qq --no-sandbox'
```

The last line starts this particular layout; do not start two QQ instances. Check paths if the installer changes them. Scan the terminal QR code using mobile QQ and complete official verification.

On **Windows**, download the official Windows Shell one-key package from [NapCat releases](https://github.com/NapNeko/NapCatQQ/releases), follow its instructions and run `napcat.bat`; do not use the tablet proot command. On a **Linux computer**, follow the [official Shell guide](https://napneko.github.io/guide/boot/Shell), inspect the installer and select local CLI mode rather than accidentally choosing Docker.

Open `http://127.0.0.1:6099/webui/` in a browser on the host. Obtain the login token from local startup logs; it is not the QQ password. Opening 127.0.0.1 on a phone accesses the phone itself. Remote access needs a separately authenticated tunnel; do not expose port 6099 publicly.

## 4. Connect AstrBot, NapCat and the chat API

Open `http://127.0.0.1:6185` on the same host. Use the initial credentials shown in AstrBot's startup output and set your own password after login. Add a QQ/aiocqhttp platform with an ID you choose, such as `myqq`. Start its OneBot v11 reverse WebSocket receiver on 127.0.0.1 port 6199 and generate a local access token.

In NapCat network settings, add a **WebSocket client**, using `ws://127.0.0.1:6199/ws`, array message format and the same token as AstrBot; enable and save it. Do not configure two servers. The two proot environments usually share the tablet's network namespace, but verify actual connection logs; Docker or virtual machines require different address planning.

Configure your own chat API and an actually available model ID in AstrBot's providers, selecting it for the current conversation. Do not assume a text-only DeepSeek model supports images; configure an actual vision provider separately. Add your QQ account as an AstrBot administrator.

First send an ordinary private message to the test QQ account. Confirm NapCat receives it, WebSocket connects, the AstrBot model call succeeds and QQ receives the reply. In a test group, mention the bot and check wake conditions. Do not enable autonomous browsing and public comments yet.

## 5. Install the main plugin

After downloading this repository, copy only the `astrbot_plugin_fish_capabilities` folder into the actual AstrBot `data/plugins/` directory. The path should resemble `AstrBot/data/plugins/astrbot_plugin_fish_capabilities/main.py`, without an extra repository-directory layer.

For computer source deployment, clone this repository beside AstrBot. Windows PowerShell example, from inside AstrBot:

```powershell
git clone https://github.com/FigaroGao/astrbot-fish-capabilities.git ../fish-capabilities
Copy-Item -Recurse ../fish-capabilities/astrbot_plugin_fish_capabilities ./data/plugins/
uv pip install --python .venv/Scripts/python.exe -e '../fish-capabilities[bilibili,speech]'
```

For Linux or **after entering Ubuntu using `astr shell` on the tablet**, change to the actual AstrBot directory and verify `.venv/bin/python` exists:

```bash
git clone https://github.com/FigaroGao/astrbot-fish-capabilities.git ../fish-capabilities
cp -r ../fish-capabilities/astrbot_plugin_fish_capabilities data/plugins/
uv pip install --python .venv/bin/python -e '../fish-capabilities[bilibili,speech]'
```

If Ubuntu has no uv, use that Python environment's own pip for the same dependencies, not native Termux pip. The `speech` and `bilibili` extras are optional for recognition and browsing and may be omitted when unused. Install FFmpeg inside the Ubuntu running AstrBot using `apt update` and `apt install ffmpeg`; on Windows, add FFmpeg to PATH. Reload the plugin or restart AstrBot without restarting an already-online NapCat.

## 6. Configure and verify individually

Initially fill only your own `owners` and `command_platform_ids` in the plugin, and add the owner as a core administrator. A UMO is the framework's complete session identifier, not merely a group number; obtain it from actual local events/configuration. Enable `enabled` and `weather_enabled` and ask for Hong Kong weather privately. Enable further capabilities only after a successful tool result.

| Capability | Additional requirements |
| --- | --- |
| Private group-history queries | `history_enabled` and your `history_group_sessions`; accumulate local records first, with no guarantee of complete history |
| Memes | Import images you may use and approve index IDs; see the [meme guide](memes.en.md) |
| Bilibili | SDK in the same Python environment, separate account QR login and correct bindings; see [interaction](bili-social.en.md); writes and review are enabled separately |
| Valorant shop | `valorant_enabled`, local WeChat authorization for your mainland account; point tool `ASTRBOT_ROOT` at actual AstrBot instead of copying the tablet default |
| Cloud memory | Your embedding provider and compatible LivingMemory; do not import someone else's store or casually change an existing index's dimensions |
| Timetable, timeline, memory corrections, ASR | Enable individually using the [0.7.0 guide](release-0.7.0.en.md); installing the plugin does not activate everything |
| Group intent | Follow [intent integration](intent.en.md) and stop on patch mismatch; basic text chat does not require this patch |

Tools must actually be allowed for the current model. A model saying it can use a tool is not a receipt. Test reads before writes, and private chat before groups. Use a dedicated account for public comments/status posts and authorize account actions explicitly in your own configuration.

## 7. Persistence, recovery and routine startup

On HarmonyOS, permit Termux background activity, autostart and exemption from battery optimization, and lock it in recent apps. A wake lock addresses only some sleep behavior and does not guarantee survival. The browser is just a WebUI; closing it should not itself stop background services. Use tmux or service supervision to retain terminal processes and verify the host environment before configuring boot startup.

After reboot, run `termux-wake-lock` in native Termux and start AstrBot and NapCat using your existing management method; do not reinstall. If no NapCat manager exists, use the command in section 3. When a recovery manager/service already exists, inspect its state instead of starting a second QQ instance. Invalid QQ credentials may still require phone verification.

For unattended recovery, read the [recovery guide](recovery.en.md), adjust actual paths and back up first. That installer targets Termux/runit, not a universal Windows service. On computers, begin with OS service supervision and make your own sleep settings. Restarting a process does not bypass QQ verification.

## 8. Acceptance and troubleshooting

| Symptom | First checks |
| --- | --- |
| WebUI works but QQ does not reply | QQ online state, reverse WS, token, AstrBot platform, model API and wake rules; three accessible WebUIs do not establish the message chain works |
| Architecture/build errors | Linux wheels accidentally installed in native Termux, Python 3.12/ARM64 compatibility; retain the actual exception |
| Tool unavailable | Master and individual switches, owner plus administrator, platform ID, session scopes, model tool access and plugin-load logs |
| Task did not run | Actual task ID from the list, Hong Kong time, switches and execution receipts; missed times are not replayed in bulk |
| Memory identifies the wrong owner | Do not copy another person's prompts or database; inspect provenance and scope using the [privacy guide](privacy.en.md) |
| QR scanned but verify fails | Continue the existing pending-verification flow using the local login tool and check account ownership; do not disclose cookies or start parallel QR flows repeatedly |

Test text, weather, authorized group scopes, a period under screen lock and network recovery, recording actual outcomes. Mark anything not run as unverified. Deployers must explicitly arrange any public-write test. Keep backups outside the repository and WebUIs off the public internet.
