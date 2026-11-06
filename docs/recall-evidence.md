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
| `lookup_unavailable` | 摘要检索失败或不完整且无可返回证据，不能判断有无记录 |

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
| `lookup_unavailable` | Summary lookup failed or was incomplete, with no returnable evidence; record existence is undetermined |

After a direct miss, the bridge checks at most three LivingMemory records and their linked sources, returning at most two archived excerpts. It reuses the memory service, creates no new vector database, and does not query automatically on every turn. Summary retrieval may use the existing embedding service; all evaluations for this change use mocks, with no paid evaluation calls.

Summaries, source candidates, and verified originals are labeled separately. Finding a related original does not validate every detail of a summary. `date_verified` refers only to the recorded message-time provenance, not the occurrence time of the described event. Summary timestamps cannot substitute for original message timestamps. Dates alone never establish a source relationship.

Returning summaries or source candidates activates the existing private cold-context quarantine before public publishing. Unavailable or partial lookup is explicitly marked, cancellation propagates, and limits are not bypassed through repeated calls.


## 来源匹配补充 / Source matching details

来源消息按原冷档的1200字片段边界对齐，单条来源最多检查前9600字，优先选最多两个包含关键词或中文相邻双字线索的片段。该本地排序只帮助定位，不是语义或事实证明。完整来源片段须全文匹配；短证据指针则须完整字面包含，不能只凭相同开头关联。极长来源超出检查窗口、完全无字面交集的同义表述仍可能只返回未核验摘要。

Cold-archive文件的时间、角色、会话、人格、片段编号、来源、日期和文本均与已有索引交叉核验；校验不通过不返回为可信片段。这是对文件与索引一致性的检查，不是对数据库之外事件真实性的证明。

Source messages align with the archive's 1,200-character chunk boundaries. At most the first 9,600 characters per source are considered, selecting up to two chunks by keywords or adjacent Chinese character-pair overlap. This local ranking locates candidates; it is not semantic or factual validation. Full stored-source chunks require a complete text match; shorter evidence pointers require their entire literal text to be contained. A common prefix alone cannot establish a match. Extremely long sources beyond the bounded window, or paraphrases with no lexical overlap, may still return only an unverified summary.

Archive-file timestamps, roles, scopes, personas, chunk numbers, sources, dates, and text are checked against the existing index. Inconsistent files are not returned as verified excerpts. This checks file/index consistency, not the truth of events outside the database.


## 并发与失败恢复 / Concurrency and failure recovery

冷档频率检查与本次查询记录在同一SQLite写事务中完成，避免多个实例先同时读取旧计数再各自通过。事务只覆盖本地检索，不跨越Embedding或其他异步等待。摘要查询取消后，已执行的冷档查询仍计入原预算，不以取消绕过冷却。一条摘要或来源读取失败只将结果标为不完整，并继续检查本次已经取得的其他候选；不会重新发起搜索。全部查询失败时返回 `lookup_unavailable`，不伪装成 `no_match`。

The cold-archive frequency check and query record run in one SQLite write transaction, preventing separate instances from reading stale counters and both passing. The transaction covers local lookup only, never embedding or other asynchronous waits. Cancelling summary retrieval does not refund an already performed cold query or bypass its cooldown. A failed summary/source read marks the result partial and allows checking other candidates already returned by this search; it does not start another search. Failure without returnable evidence produces `lookup_unavailable`, rather than `no_match`.
