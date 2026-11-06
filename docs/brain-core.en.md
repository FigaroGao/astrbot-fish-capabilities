# Brain Core: shared decisions and incremental fixes

[中文](brain-core.md) | [English — full translation](brain-core.en.md)

This update connects existing QQ, Autonomy, Bilibili and Screenmate decisions to shared working state and attention coordination while reusing existing executors. The core does not implement every tool or require an additional model decision for every event. Ordinary private chat and explicit tool requests continue through AstrBot's native flow.

## Actual integration

| Path | Shared components | Specialist capabilities retained |
|---|---|---|
| QQ group participation | Per-group decision leases, owner-interaction priority, checks before sending | Existing intent assessment, complex-task filtering, group silence and complete segmented delivery |
| Autonomous activities and private initiation | Owner attention lane, current work, preemption and delivery leases | Existing completion-relative Autonomy cooldown, small related action chains, private candidates and budgets |
| Bilibili selection and interaction | Work progress, candidate topics and public-write coordination | Multistage video understanding, identity verification, existing public review and shared budgets |
| Screenmate | Shared proactive decisions and contact cooldown | Capture, pet actions, voice and playback receipts remain in the [separate repository](https://github.com/FigaroGao/Xiaojing-Screenmate) |

`services/brain.py` manages short-term attention and leases. `brain_context.py` reads the existing AstrBot persona and adds task context. LivingMemory remains the long-term memory service. Independent review, extraction and visual analysis do not receive the complete persona or private chat. Working state records when a message was observed rather than presenting a past interaction as an ongoing conversation.

## Fixed behavior

- Owner input can invalidate an older proactive decision. Expired or replaced model results cannot continue acting. An old autonomous cycle cannot clear a new instance's lease or overwrite its working state.
- Explicit group requests do not expire merely because other members keep chatting. Follow-ups by the original speaker, new explicit requests and silence controls can still affect an old draft. Missing context is not interpreted as consent.
- Preemption before any send is distinguished from partial delivery and unknown network outcomes. The former can release reservations; the latter are not automatically resent. Cancellation during public transport also preserves uncertainty and duplicate protection.
- Overlapping private checks no longer clear an in-flight activity note. Generated drafts are distinguished from text accepted by the adapter; adapter acceptance does not prove the recipient read it.
- Actually read videos can become source-grounded topic candidates without immediate recommendations. Ordinary private chat can declare candidate use through the existing `fish_bili_memory` tool's optional `use_topic_id`. Discussion is recorded only after the complete normal model text is accepted by the adapter. Tool acknowledgements, partial sends, errors and expired plans do not count. Undeclared use or paths bypassing ordinary send are not guessed to have consumed a topic.
- Unfinished tool chains retain complete material and necessary protocol fields; completed turns are compacted afterward. Historical video material retains source timestamps, reading IDs and each summary/reflection's original basis. An old reflection cannot replace a newer source packet.
- Rolling-summary chunks are independent JSON. Oversized messages repeat their original role and tool reference. A user role is not automatically treated as the owner. Summary locks survive hot reloads to avoid duplicate generation for the same history.
- Long historical tool results retain failure and submission/verification flags. Generic JSON becomes an explicitly truncated preview; an empty query does not establish that something never happened.
- New pending notes no longer crowd approved expression references out of recall. Versioned edits are transaction-protected, and expired or archived records are not automatically revived. Repeated-opening hints act before generation, without banning forms of address, mechanically rewriting replies afterward or adding a polishing model call.
- Specific character names take precedence over family aliases within the same mention. Multi-image observation separates speakers inside images, quotations and user-provided identity statements; avatars and bubble positions do not establish current identity. New public editorial definitions in `knowledge/conversation` and `knowledge/culture` retain sources and dates.

## Installation and upgrades

Start with [deployment from scratch](getting-started.en.md), install this repository's capability plugin and required dependencies, then configure your own owner identity, platform, authorized groups and services. Shared feature switches default to off. Personal character cards, memories, letters, login sessions and API keys are not distributed.

Before upgrading, back up plugin source, configuration and plugin data. Check AstrBot compatibility, persona resolution and tool registration in a test conversation before enabling capabilities individually. SQLite tables or keys are added as needed; source rollback must not overwrite chats and receipts created after the upgrade. The Screenmate bridge needs the matching shared-core interface from its separate repository. Updating this repository alone does not update the desktop component.

## Validation and limitations

The latest complete maintenance-checkout regression run passed 788 tests. The publication checkout is also tested after synchronization; see [validation](validation.en.md) for its final result. Earlier production-device checks covered shared instances, preemption, deduplication, lease release, topic receipts, provenance and summaries. QQ was online at that check, and 40 personal character cards remained intact. Tests use temporary databases and mock transports, not proof that subjective conversational quality is fully accepted.

The device is disconnected during this GitHub synchronization, so no new deployment or restart is performed. Actual pronoun understanding, natural expression, topic-selection coverage and continuous co-viewing still require real feedback. No additional paid batch evaluation or test comments were sent. Permissions, private/group isolation and public review remain in force.

Not yet fixed: an audit found that a scheduled task paused or revised by another instance while awaiting an intent decision may lack a second check before execution. This update records the issue rather than claiming it is repaired. Incremental auditing continues.


Independent publication-checkout regression: 789 tests passed, with one existing audioop deprecation warning. This is not added to the maintenance-checkout count; the tablet was not connected for this publication.
