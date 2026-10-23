# Sharing-release validation: 2026-10-24

[中文](validation.md)

The 0.4.0 sharing directory was retested: `pytest -q tests` **167 passed**; `unittest discover -s recovery -p 'test_*.py'` **6 passed**. These 173 tests use synthetic messages and fake endpoints. pytest-asyncio is required; skipped asynchronous tests without that dependency are not a complete pass. Dependencies are in the root `.[test]` extra.

Coverage includes authorization, intent concurrency, media budgets, usage, Bilibili callbacks and identity verification, comment boundaries, video memory, previews, group approval, initiative budgets, context summaries and failure retention, knowledge retrieval, and recovery guarding. Original-device checks included plugin loading, public Bilibili reading and QR verification, real knowledge queries, context migration/cache reuse, ordinary long-text segment components and core decisions, manager restart after exit, and missing-service repair.

Real public comments, actual password fallback, Tencent verification, whole-device reboot, 27-frame visual coverage across all videos, and ARM64 compatibility across every version were not verified. This publication did not restart QQ or send group test messages. Final phone rendering and the complete message chain still need normal-conversation checks. The newly packaged installer received syntax and path-logic checks without reinstalling the existing device. Passing tests do not guarantee permanent uptime.
