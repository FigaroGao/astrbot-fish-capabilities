# Fish: AstrBot conversation capabilities

[中文](README.md) | [English](README.en.md)

An experimental, privacy-scrubbed extension extracted from an ARM64 HarmonyOS tablet running Termux, Ubuntu proot, NapCat and AstrBot. See the Chinese documentation for complete setup instructions.

Implemented: on-demand weather, owner-only access to authorized group history, owner command restrictions, DeepSeek balance and recorded usage, intent-based group participation, serialized replies including segmented delivery, and indexed reaction images chosen by the model.

All capabilities are disabled by default. Replace every `YOUR_*` placeholder in `examples/config.disabled.json`. The owner must also be an AstrBot administrator. Group permissions use complete session identifiers, not just group numbers.

Reference runtime: AstrBot 4.29.1 and NapCat 4.18.38 with Python 3.12 in Ubuntu proot. Intent routing requires the separately documented Group Chat Plus bridge. The patch baseline was already customized; check compatibility before applying. This is not a universal one-click installer.

The cleaned export passed 103 local tests. Prior device checks included plugin loading, synthetic intent scenarios, reply-pipeline locking and one private image delivery acknowledged by NapCat. Local tests do not establish compatibility with every framework version or full QQ connectivity.

No credentials, conversations, memory databases, personal configuration or third-party image assets are included. Import your own approved images with `python -m tools.import_meme`. Automatic images require three reply turns and a 180-second cooldown, with additional hourly and duplicate-image limits. Explicit requests may bypass the turn/cooldown limits, but not all limits.

Long-term memory uses a separate customized LivingMemory installation; that full adaptation is not included. Bilibili, voice and device-control prototypes are disabled and have not completed device acceptance testing. Automatic password-based QQ recovery is not implemented.

```bash
python -m pip install -e '.[test]'
python -m pytest -q tests
```

AGPL-3.0; see LICENSE and NOTICE.md for upstream attribution and third-party boundaries.
