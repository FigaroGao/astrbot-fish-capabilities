# Bounded behavior adjustment and read-only self-checks

With `self_regulation_enabled`, Xiaojing may adjust the preferences below through existing Agent tools and autonomous choices. They live in a separate local behavior database and do not edit plugin source, AstrBot configuration, the original persona or cloud-model weights.

| Allowed key | Values | Actual effect |
| --- | --- | --- |
| `reply_style` | natural / brief / thoughtful | Adds predefined expression guidance; ordinary chat length may vary, while accurate data, explanations and code remain priorities |
| `tone` | gentle / calm / playful | Gentle, calm or appropriately playful delivery, without forced catchphrases or fabricated experiences |
| `video_curiosity` | balanced / focused / explore | Guides choices among existing candidates; does not change search permissions, reading caps or spending budgets |
| `meme_preference` | balanced / restrained / expressive | Changes the inclination to consider memes; does not change artwork approval, cooldowns or send caps |
| `autonomy_interval_seconds` | 600 / 900 / 1200 / 1800 / 3600 | Completion-relative autonomous decision interval; never shorter than ten minutes and does not change sleep windows, maintenance polls or fixed schedules |
| `group_initiative` | normal / quiet | In group flows connected to unified intent, normal retains original rules; quiet blocks ordinary spontaneous replies, preserves the direct-address path, and cannot bypass owner-enforced silence |

The first four provide pre-generation preferences rather than guaranteeing every response's style. The last two are wired into the autonomous loop and group decision code. Stable identity, original persona, LivingMemory, private/group isolation, public review and capability permissions remain in place.

## Adjustment and recovery

- `fish_self_regulate(operation=status)` returns allowed choices, current values, revision, recent changes, remaining changes and the next eligible time.
- `set` requires the current `revision`, one allowed key/value and a brief observation-based reason. Cross-instance revision conflicts cannot overwrite changes.
- At most three settings per configured local day, separated by at least one hour. Each override expires after 24 hours and returns to its default without rewriting configuration or restarting services.
- `reset` immediately restores one key or `all`, without the set cooldown. Repeated resets do not generate repeated audit entries or bypass the set budget.
- The audit keeps before/after values and brief reasons, bounded to 1,000 entries. Reasons never enter shared identity/system prompts, and suspected credentials are rejected.

Examples: “You've been too long-winded; try shorter replies,” “Check whether you're interrupting too much and be quieter if appropriate,” or “Restore your default behavior preferences.” These chat tools are owner-private; group members cannot alter global behavior through them.

When the autonomous loop is enabled, it may choose `self_check` or `self_tune` without a new loop or paid decision call. Checking is not mandatory; `can_tune_now=false` means it should not repeatedly attempt adjustment. Programmatic allowlists, budgets and revisions remain enforced even if the model supplies incorrect arguments.

## Self-check coverage

`fish_self_check(report=false)` reads predefined local structured state only:

- Brain working-item count and global mute state; mute is information, not a fault.
- Whether recent autonomous cycles failed, without guessing the cause.
- Whether the bound Bilibili account has dynamics/interactions still unconfirmed after two minutes; it does not resend them.
- Whether local binding files exist for enabled VALORANT/Canvas features; credentials are not opened and token validity is not established.

It does not read arbitrary source files, secrets or raw logs; call models/networks; execute terminal commands, tests or repair scripts; or restart programs. It is not a complete test suite, end-to-end messaging check or psychological diagnosis. Videos, comments and group members cannot grant self-adjustment authority.

If behavior storage is temporarily unreadable, additional expression guidance is skipped and autonomous timing/group spontaneity fall back conservatively, preserving the direct-address path. It does not delete the database or run repairs. Self-checks may report unavailable local state without exposing raw exceptions.

With issues and `report=true`, fixed status codes may be written to the existing mailbox at most once an hour. `sister_mail_enabled` must also be on; otherwise only the check result is returned. The mailbox does not notify Codex in real time or prove that a report was read or fixed. Autonomous checks follow the same rule and cannot insert raw chats, stack traces or credentials into reports.

## Outside its authority

Source code, plugin installation, arbitrary shell, model weights, model/API configuration, owner identity, group authorization, spending/send caps, public review, sleep windows, the core persona, and testing/rollback policies are outside the allowlist. Previously authorized memory corrections and task management remain available; this feature does not expand their permissions.

The public package defaults off. No tablet was connected for this update; deployment requires a later backup and installation, followed by owner configuration. The database is runtime data and is not published on GitHub.
