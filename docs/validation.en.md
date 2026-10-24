# Sharing-release validation: 2026-10-25

[中文](validation.md)

The 0.5.0 sharing directory was retested: `pytest -q tests` **263 passed**; `python -m unittest discover -s recovery -p 'test_*.py'` **18 passed**. The **281 tests** use synthetic messages, temporary directories and fake endpoints rather than real passwords or public comments. Dependencies are in the root `.[test]` extra; pytest-asyncio is required, and skipping asynchronous tests because dependencies are missing is not a complete pass.

## Coverage in this release

Plugin tests cover authorization and private-chat isolation, intent concurrency, media budgets, usage, Bilibili QR callbacks and identity checks, homepage recommendations, public likes and favorites scope, comment mention mapping and visibility classification, zero-value semantics for unlimited reading budgets, preview images, group approval, private-initiative budgets, context summaries and failure retention, public knowledge, homophone hints, depth guidance, complex group-task filtering, the mailbox, and VALORANT login state, match fields and incremental cache reads.

Recovery tests comprise 12 state-machine tests and 6 independent-guard tests. They cover waiting for native recovery, readiness checks, two quick-login attempts and one password fallback, persisting attempt counts before a request can time out, stopping for manual verification, waiting for QR scanning without a password, unreachable WebUI, cooldowns and guard repair boundaries. See the [recovery guide](recovery.en.md).

## Device checks and limits of the evidence

Earlier checks on the original device included plugin loading, public Bilibili reading and QR verification, real knowledge queries, context migration and cache reuse, ordinary long-text segmentation components and core decisions, manager restart after exit, and missing-service repair. Before this release, read-only checks showed the recovery manager as `online` and the independent guard as `healthy`; the manager source matched the live file. The owner's report of recent stable operation is operational feedback, not a permanent-uptime guarantee.

This publication did not restart QQ on the tablet, reinstall recovery, deliberately disconnect the account or send group test messages. No private configuration, account bindings, match records, conversations, mailbox contents or runtime logs were published.

Real public comments and notification delivery, actual password fallback, Tencent identity verification, full-chain recovery after a device reboot, 27-frame visual coverage across all videos, and ARM64 compatibility across all software versions were not tested. Final segmentation as displayed on a phone and the complete chain from QQ online through OneBot to AstrBot message receipt still require normal-use verification; one online flag cannot replace an end-to-end test. The packaged installer received syntax and path-logic checks without reinstalling the existing device.
