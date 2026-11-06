# Recall evidence and summary indexes / 原文回忆与摘要索引

## 中文

`fish_recall` 仍仅供主人私聊使用，沿用原人格、会话隔离及查询预算。

| 状态 | 含义 |
| --- | --- |
| `found` | 本次关键词命中经过文件校验的冷档片段 |
| `no_match` | 本次线索未命中，不证明过去没说过 |
| `cooldown` / `same_cue_recently_read` / `daily_limit` | 本次没有检索；等待 Unix 秒 `retry_at`，不可换词绕过 |
| `found_via_summary` | 通过同范围 LivingMemory 摘要的来源指针找到冷档片段 |
| `summary_only` | 命中摘要，但原文仍未确认 |

直接搜索未命中时，最多检索三个 LivingMemory 条目及关联来源，最终最多返回两段冷档原文。复用既有记忆服务，不新建向量库，不每轮自动查询。摘要查询可能使用既有 Embedding 服务；本次测试均用 Mock，没有付费评测。

摘要、来源候选、已校验原文分别标注，找到相关原文也不等于摘要每个细节都成立。`date_verified` 仅表示冷档记录的消息时间来源，不代表所述事件的发生时间；摘要时间不能代替原消息时间。没有来源关系时不凭日期猜测。

返回摘要或来源候选同样触发已有冷档私有上下文隔离，不直接携带到公开发布。服务不可用或查询不完整时明确标记，保留取消传播，不重复调用绕过预算。

## English

`fish_recall` remains owner-private, with the existing persona/session boundaries and query budgets.

| State | Meaning |
| --- | --- |
| `found` | This keyword search found checksum-verified cold-archive excerpts |
| `no_match` | These clues did not match; this does not prove something was never said |
| `cooldown` / `same_cue_recently_read` / `daily_limit` | No lookup was performed; wait until Unix-seconds `retry_at`, without changing clues to evade limits |
| `found_via_summary` | A scoped LivingMemory summary source pointer led to an archived excerpt |
| `summary_only` | A summary matched, but its original remains unverified |

After a direct miss, the bridge checks at most three LivingMemory records and their linked sources, returning at most two archived excerpts. It reuses the memory service, creates no new vector database, and does not query automatically on every turn. Summary retrieval may use the existing embedding service; all evaluations for this change use mocks, with no paid evaluation calls.

Summaries, source candidates, and verified originals are labeled separately. Finding a related original does not validate every detail of a summary. `date_verified` refers only to the recorded message-time provenance, not the occurrence time of the described event. Summary timestamps cannot substitute for original message timestamps. Dates alone never establish a source relationship.

Returning summaries or source candidates activates the existing private cold-context quarantine before public publishing. Unavailable or partial lookup is explicitly marked, cancellation propagates, and limits are not bypassed through repeated calls.
