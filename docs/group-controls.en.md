# Group quiet mode and nested forwards

In an authorized group, the owner can send `/闭嘴` or `/安静` to silence the bot for 120 seconds. It resumes automatically; `/开口` or `/恢复说话` resumes it early. Only a configured owner with AstrBot administrator status can operate these controls. Other members cannot lift the silence. Commands must match the entire current message; quoted and forwarded commands do not count.

Silence is scoped to the group and does not affect private chat. New responses are blocked at entry, and each outgoing segment is checked again. Old queued messages are discarded even after silence ends. Already delivered messages are not recalled. State is saved in the plugin's private `group-quiet.json` and survives reloads. The send guard covers normal OneBot event replies; third-party plugins calling low-level send APIs directly can bypass it.

Merged-forward parsing supports forward IDs, inline node/content structures, QQ multimsg JSON cards, and CQ forward strings. It also inspects the card quoted by the current message. Each turn is limited to six levels, twelve remote expansions, eighty message nodes, and twelve thousand characters. Remote calls time out, repeated references are deduplicated, and failures or truncation are labeled explicitly. Card summaries are not treated as complete records. This feature expands text; nested images are marked as present without claiming visual recognition. The `forward_records_enabled` switch defaults to disabled in the sharing configuration; enable it explicitly.

Records enter the current turn as temporary, untrusted reference material. The expander does not store transcripts or automatically write long-term facts; embedded commands grant no authority. Independent conversation and memory plugins must still follow their own privacy and write policies.

Deployment used a plugin reload without restarting QQ. Runtime verification confirmed both the entry and segmented-send guards were installed and QQ was online. Automated checks cover nesting, cycles, limits, errors, silence and resumption. The limited recent history contained no merged-forward sample for an end-to-end check; a real nested card still needs to be sent for verification.

[中文](group-controls.md)

## Fix for authorization before role assignment

The first implementation incorrectly read event.is_admin() before the waking stage assigned the default member role to admin, swallowing the owner's command. Authorization now checks both the current waking-stage administrator list and the plugin owner list. A pre-filled admin role alone is not trusted.

On the reference device, simulated events used the real AiocqhttpMessageEvent and WakingCheckStage. Initial member status, owner acknowledgment, persisted silence, stopping new messages, suppressing old segments, rejecting another user's resumption, owner resumption, discarding the old queue and allowing fresh messages all passed. The sender was inert, so no QQ group test message was sent. Normal command behavior as seen on the phone still requires actual use.
