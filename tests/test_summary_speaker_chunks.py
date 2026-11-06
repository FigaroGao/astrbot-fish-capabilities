import asyncio,json
from types import SimpleNamespace
from astrbot_plugin_fish_capabilities.services.context_budget import summary_chunks,ContextBudget
from test_context_budget import history


def test_message_chunks_are_valid_json_and_keep_original_roles():
    rows=[{'role':'user','content':'甲说我在上课'*1000}, {'role':'assistant','content':'这是机器人自己的猜想'*1000}]
    chunks=summary_chunks(rows)
    decoded=[row for chunk in chunks for row in json.loads(chunk)]
    assert all(len(chunk)<=16000 for chunk in chunks)
    assert decoded==rows


def test_oversized_quote_keeps_speaker_and_tool_reference_on_every_fragment():
    row={'role':'tool','tool_call_id':'call-quoted','content':'截图中乙说“我在家”\\这是引文'*3000}
    chunks=summary_chunks([row]);pieces=[p for chunk in chunks for p in json.loads(chunk)]
    assert len(pieces)>1 and all(len(c)<=16000 for c in chunks)
    assert all(p['role']=='tool' and p['tool_call_id']=='call-quoted' and p['continued_message']==0 for p in pieces)
    reconstructed=json.loads(''.join(p['serialized_message_fragment'] for p in pieces))
    assert reconstructed==row


async def test_summary_generation_never_receives_roleless_json_slice(tmp_path):
    seen=[]
    async def generate(prompt):
        assert 'role=user只表示消息角色' in prompt and '各群成员、引用说话人' in prompt
        content=prompt.split('旧片段（独立JSON，原消息或带归属的超长分片）：',1)[1]
        seen.extend(json.loads(content));return '区分了用户原话和机器人猜测的摘要'
    rows=history(20)
    for row in rows:row['content']+='材料'*700
    budget=ContextBudget(tmp_path/'summary.db',generate)
    _,stats=await budget.prepare('private-scope',rows)
    assert stats['outcome']=='summarized' and seen==rows[:-16]


async def test_reload_instances_share_summary_lock_and_reuse_completed_prefix(tmp_path):
    coordinator=SimpleNamespace();entered=asyncio.Event();release=asyncio.Event();calls=[]
    async def generate(prompt):
        calls.append(prompt);entered.set();await release.wait();return '有来源的滚动摘要'
    first=ContextBudget(tmp_path/'summary.db',generate,coordination=coordinator)
    second=ContextBudget(tmp_path/'summary.db',generate,coordination=coordinator)
    assert first.locks is second.locks
    one=asyncio.create_task(first.prepare('scope',history(20)));await entered.wait()
    two=asyncio.create_task(second.prepare('scope',history(20)));await asyncio.sleep(0)
    assert len(calls)==1 and not two.done()
    release.set();await one;_,stats=await two
    assert stats['outcome']=='reused' and len(calls)==1
    different=ContextBudget(tmp_path/'other.db',generate,coordination=coordinator)
    assert different.locks is not first.locks
