# Recovery deployment and validation

[中文 — 完整对应版本](recovery.md)

## Boundaries

The reference is NapCat 4.18.38. Let NapCat handle its own Worker and session recovery first. The external manager only calls existing login APIs; it does not kill QQ or restart its Worker. It polls login status and does not claim to automatically verify the complete OneBot → AstrBot → model chain after each recovery. Recheck endpoints and response fields after upgrading NapCat.

States include online, waiting for native recovery, quick-login requested, password-login requested, manual verification required, waiting for QR login without a password, attempts exhausted, and WebUI unreachable. Checks run about every 30 seconds. Retry budgets persist and a single-instance file lock prevents concurrent flows. Errors record stages/types, not raw responses or passwords. State files are private runtime data too.

## Installation

Run `pkg install python termux-services` in native Termux. Edit the top-level `WEB` path in `recovery/napcat_recovery.py` to point to the actual NapCat `config/webui.json`. The default uses the proot-distro `napcat` container and `/root/Napcat/opt/QQ/`. Do not copy the original device's webui.json.

Run `python recovery/install.py` and enter the QQ account locally. The installer refuses to overwrite an existing service or manager files. Back up and compare an existing installation rather than installing repeatedly. This installer is newly packaged for sharing; an offline syntax check does not establish installation testing on every tablet.

The service directory is `$PREFIX/var/service/fish-recovery`, the manager is `~/.napcat-recovery/manager.py`, and settings are in its sibling `settings.json`. Enter an optional password locally with `set-password`; its digest can log in and must be protected like the password itself. `remove-password` disables that fallback. The installer neither restarts nor logs out QQ.

## Recovery flow

1. A fully online QQ state clears the current offline and retry state.
2. After offline detection, wait 120 seconds. Do not compete with login while initialization, reconnection, or a scanned QR flow is in progress.
3. Attempt quick login at most twice, at least 300 seconds apart. Save the attempt before sending; unknown outcomes still count.
4. Without a configured password, wait for scanning. With one configured, attempt password login at most once.
5. Tencent captchas, identity / security / new-device verification, frozen accounts, and wrong passwords require human handling. No password loop or verification bypass is attempted.
6. After official verification on the phone, run `python ~/.napcat-recovery/manager.py resume` to allow a new bounded round. Phone verification does not guarantee that the old session is reusable. If scanning is still required, use the local NapCat login flow.

Inspect `python ~/.napcat-recovery/manager.py status`. `webui_unreachable` means the API cannot confirm status, not proof that QQ is offline or justification to kill it.

## Guarding, pausing, and stopping

runit restarts the manager if that process exits. `finish` waits 5 seconds, and `svlogd` rotates logs. `service-exits.log` records the manager's exit code and signal; it does not automatically capture output from another QQ instance already running in a terminal.

Optionally load `astrbot_plugin_fish_host_guard` to execute native `ensure_services.py` every 60 seconds. It checks the manager lock, state freshness, and official runsvdir process. If absent, it starts the official service-daemon and only fish-recovery. A manager holding its lock without updating for 180 seconds triggers only a manager restart. Repairs are limited to 3 per hour, 180 seconds apart, with the budget saved first.

```bash
# Pause the guard before maintenance, then stop the manager; QQ stays running
touch ~/.napcat-recovery/host-guard.pause
sv down "$PREFIX/var/service/fish-recovery"
# Resume after maintenance
rm ~/.napcat-recovery/host-guard.pause
sv up "$PREFIX/var/service/fish-recovery"
```

If the whole Termux app or AstrBot stops, this setup cannot revive it from outside Android. Boot autostart, a public recovery endpoint, and phone push notifications are not promised or deployed. Keeping a browser in the background does not replace service supervision.

## Validation boundaries

Synthetic state and isolated guard tests cover budgets, cooldowns, verification stops, API failures, and missing-service repair. On the original device, runit restarted an individually terminated manager, and previously missing services were restored while the QQ process and ready status remained intact. The exact cause of the earlier exit was not established; old OS cleanup records are not proof of that incident's cause.

Tests did not deliberately cause server-side QQ logout, exercise a real password login, trigger account-risk verification, or reboot the device. After recovery, still confirm QQ online status, an attached OneBot WebSocket, and receipt and successful reply to a normal AstrBot message. Login success alone is not end-to-end recovery.
