from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
import pytest
from test_cold_memory import archive,S
from test_astrbot_binding import plugin
from astrbot_plugin_fish_capabilities.services.recall_bridge import summary_fallback

def engine(scope=S,source=True):
    return NS(search_memories=AsyncMock(return_value=[NS(doc_id=7)]),
        get_memory_record=AsyncMock(return_value={'text':'豆瓣酱放多了，偏咸，日期只是摘要标注','metadata':{'session_id':scope,'persona_id':'p'}}),
        get_memory_source=AsyncMock(return_value=[{'role':'user','sender_id':'10001','content':'今天豆瓣酱倒多了，整盘咸了','timestamp':123}] if source else []))

async def test_summary_source_returns_verified_archive_not_summary_date(tmp_path):
    cold,clock=archive(tmp_path);cold.capture(S,'p','user','今天豆瓣酱倒多了，整盘咸了','fixture')
    result=cold.recall(S,'p','豆瓣酱 放多了')
    assert result['state']=='no_match'
    out=await summary_fallback(cold,engine(),S,'p','豆瓣酱 放多了',result)
    assert out['state']=='found_via_summary' and out['excerpts'][0]['original_text_verified']
    assert out['excerpts'][0]['date_verified'] and not out['source_candidates'][0]['date_verified']
    assert not out['source_candidates'][0]['summary_equivalence_verified']

async def test_summary_without_original_is_explicitly_unverified(tmp_path):
    cold,_=archive(tmp_path);out=await summary_fallback(cold,engine(source=False),S,'p','豆瓣酱',cold.recall(S,'p','豆瓣酱'))
    assert out['state']=='summary_only' and not out['original_text_verified'] and not out['excerpts']
    assert not out['summary_hits'][0]['date_verified']

async def test_no_cross_scope_or_sender_leak(tmp_path):
    cold,_=archive(tmp_path);e=engine(scope='another:FriendMessage:1')
    out=await summary_fallback(cold,e,S,'p','豆瓣酱',cold.recall(S,'p','豆瓣酱'))
    assert out['state']=='no_match' and not out['summary_hits'];e.get_memory_source.assert_not_called()

async def test_cooldown_does_not_run_summary_lookup_or_claim_absence(tmp_path):
    cold,clock=archive(tmp_path);cold.recall(S,'p','第一次')
    out=cold.recall(S,'p','第二次');e=engine()
    assert not out['lookup_performed'] and out['existence_conclusion']=='undetermined'
    assert out['retry_at']==clock[0]+300
    assert await summary_fallback(cold,e,S,'p','第二次',out)==out
    e.search_memories.assert_not_called()

async def test_imported_snapshot_date_not_verified(tmp_path):
    cold,_=archive(tmp_path);cold.capture(S,'p','user','今天豆瓣酱倒多了，整盘咸了','fixture',time_quality='import_snapshot')
    out=await summary_fallback(cold,engine(),S,'p','豆瓣酱 放多了',cold.recall(S,'p','豆瓣酱 放多了'))
    assert out['excerpts'][0]['original_text_verified'] and not out['excerpts'][0]['date_verified']

async def test_failed_summary_search_is_not_record_absence(tmp_path):
    cold,_=archive(tmp_path);e=engine();e.search_memories.side_effect=TimeoutError('private')
    out=await summary_fallback(cold,e,S,'p','豆瓣酱',cold.recall(S,'p','豆瓣酱'))
    assert out['summary_lookup']=='unavailable_or_partial' and 'private' not in str(out)


@pytest.mark.parametrize('field,value',[('persona_id','other'),('session_id','other:FriendMessage:2')])
async def test_source_wrong_identity_not_exposed(tmp_path,field,value):
    cold,_=archive(tmp_path);e=engine()
    e.get_memory_source.return_value[0][field]=value
    out=await summary_fallback(cold,e,S,'p','豆瓣酱',cold.recall(S,'p','豆瓣酱'))
    assert out['state']=='summary_only' and not out['source_candidates']

async def test_other_sender_source_not_exposed(tmp_path):
    cold,_=archive(tmp_path);e=engine();e.get_memory_source.return_value[0]['sender_id']='20002'
    out=await summary_fallback(cold,e,S,'p','豆瓣酱',cold.recall(S,'p','豆瓣酱'))
    assert not out['source_candidates'] and not out['excerpts']

async def test_corrupt_archive_does_not_verify_summary(tmp_path):
    cold,_=archive(tmp_path);cold.capture(S,'p','user','今天豆瓣酱倒多了，整盘咸了','fixture')
    with cold.db() as db:row=db.execute('SELECT * FROM chunks').fetchone()
    path=cold.root/row['file'];path.chmod(0o600);path.write_text('{}',encoding='utf-8')
    out=await summary_fallback(cold,engine(),S,'p','豆瓣酱 放多了',cold.recall(S,'p','豆瓣酱 放多了'))
    assert out['state']=='summary_only' and not out['original_text_verified']
    assert not out['summary_hits'][0]['original_text_verified']

async def test_summary_only_quarantines_public_context(plugin):
    import json
    from test_astrbot_binding import Event
    plugin.config.update(cold_archive_enabled=True,command_platform_ids=['qq_test'],bili_private_session=S)
    plugin.context=NS(conversation_manager=NS(get_curr_conversation_id=AsyncMock(return_value='cid'),get_conversation=AsyncMock(return_value=NS(persona_id='p'))))
    plugin.memory_scope=AsyncMock(return_value=(engine(source=False),S,'p'))
    event=Event();event.unified_msg_origin=S
    out=json.loads(await plugin.cold_recall_tool(event,query='豆瓣酱'))
    assert out['state']=='summary_only'
    assert event.get_extra('fish_cold_private_context') is True
    assert plugin.cold_memory.is_private_context(S,'cid')

def test_same_cue_and_daily_limit_expose_retry_time(tmp_path):
    from datetime import datetime
    cold,clock=archive(tmp_path,'2026-10-27T10:00:00+08:00');start=clock[0]
    cold.recall(S,'p','重复线索');clock[0]+=301
    out=cold.recall(S,'p','重复线索')
    assert out['retry_at']==start+3600 and not out['lookup_performed']
    for i in range(11):
        cold.recall(S,'p',f'其他线索{i}');clock[0]+=301
    out=cold.recall(S,'p','第十三次')
    assert out['state']=='daily_limit'
    assert out['retry_at']==datetime.fromisoformat('2026-10-28T00:00:00+08:00').timestamp()


async def test_unspaced_paraphrase_uses_linked_source(tmp_path):
    cold,_=archive(tmp_path);cold.capture(S,'p','user','今天豆瓣酱倒多了，整盘咸了','fixture')
    out=await summary_fallback(cold,engine(),S,'p','豆瓣酱放多',cold.recall(S,'p','豆瓣酱放多'))
    assert out['state']=='found_via_summary'

async def test_long_source_selects_relevant_chunk_not_first_prefix(tmp_path):
    cold,_=archive(tmp_path);text='无关内容'*300+'今天豆瓣酱倒多了，整盘咸了'
    cold.capture(S,'p','user',text,'fixture');e=engine();e.get_memory_source.return_value[0]['content']=text
    out=await summary_fallback(cold,e,S,'p','豆瓣酱 放多了',cold.recall(S,'p','豆瓣酱 放多了'))
    assert out['state']=='found_via_summary' and '豆瓣酱' in out['excerpts'][0]['text']

async def test_prefix_collision_cannot_verify_different_source(tmp_path):
    cold,_=archive(tmp_path);prefix='相同开头'*60
    cold.capture(S,'p','user',prefix+'豆瓣酱倒多了，但不是所找来源','fixture')
    e=engine();e.get_memory_source.return_value[0]['content']=prefix+'豆瓣酱倒多了，所找的是另一段原话'
    out=await summary_fallback(cold,e,S,'p','豆瓣酱 放多了',cold.recall(S,'p','豆瓣酱 放多了'))
    assert out['state']=='summary_only' and not out['excerpts']

@pytest.mark.parametrize('field,value',[('at',1),('role','assistant'),('scope','other:FriendMessage:2'),('persona','other'),('time_quality','import_snapshot')])
def test_archive_time_and_speaker_tampering_rejected(tmp_path,field,value):
    import json
    from astrbot_plugin_fish_capabilities.services.policy import CapabilityError
    cold,_=archive(tmp_path);cold.capture(S,'p','user','完整原话内容','fixture')
    with cold.db() as db:row=db.execute('SELECT * FROM chunks').fetchone()
    path=cold.root/row['file'];packet=json.loads(path.read_text(encoding='utf-8'));packet[field]=value
    path.chmod(0o600);path.write_text(json.dumps(packet),encoding='utf-8')
    with pytest.raises(CapabilityError):cold.excerpt(row)


async def test_cancelled_lookup_propagates_without_claiming_absence(tmp_path):
    import asyncio
    cold,_=archive(tmp_path);e=engine();e.search_memories.side_effect=asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await summary_fallback(cold,e,S,'p','豆瓣酱',cold.recall(S,'p','豆瓣酱'))

def test_source_ranking_is_bounded_and_not_semantic_proof():
    from astrbot_plugin_fish_capabilities.services.recall_bridge import source_windows
    text='无关内容'*300+'豆瓣酱倒多了'+'其他内容'*300+'豆瓣酱用多了'
    out=source_windows(text,'豆瓣酱放多')
    assert 1<=len(out)<=2 and all('豆瓣酱' in chunk for chunk in out)
    assert not source_windows('完全不同的话','豆瓣酱放多')


@pytest.mark.parametrize('failure',[ValueError('bad metadata'),TimeoutError('source unavailable')])
async def test_one_failed_record_does_not_hide_later_source(tmp_path,failure):
    cold,_=archive(tmp_path);cold.capture(S,'p','user','今天豆瓣酱倒多了，整盘咸了','fixture');e=engine()
    e.search_memories.return_value=[NS(doc_id=6),NS(doc_id=7)]
    row=e.get_memory_record.return_value
    e.get_memory_record.side_effect=[failure,row]
    out=await summary_fallback(cold,e,S,'p','豆瓣酱放多',cold.recall(S,'p','豆瓣酱放多'))
    assert out['state']=='found_via_summary' and out['summary_lookup']=='unavailable_or_partial'
    assert out['excerpts'][0]['original_text_verified']

async def test_unavailable_lookup_state_never_says_no_match(tmp_path):
    cold,_=archive(tmp_path);e=engine();e.search_memories.side_effect=TimeoutError()
    out=await summary_fallback(cold,e,S,'p','豆瓣酱',cold.recall(S,'p','豆瓣酱'))
    assert out['state']=='lookup_unavailable' and out['existence_conclusion']=='undetermined'


def test_concurrent_instances_share_atomic_cooldown(tmp_path):
    from contextlib import contextmanager
    from concurrent.futures import ThreadPoolExecutor
    import threading
    from astrbot_plugin_fish_capabilities.services.cold_memory import ColdMemory
    first,clock=archive(tmp_path);second=ColdMemory(first.root,clock=lambda:clock[0])
    read_barrier=threading.Barrier(2)
    # Force the old unprotected read/check interleaving. A transaction that
    # obtains the write reservation before reading needs no injected barrier.
    for cold in (first,second):
        original=cold.db
        @contextmanager
        def raced_db(original=original):
            with original() as conn:
                class Proxy:
                    def execute(self,sql,args=()):
                        cursor=conn.execute(sql,args)
                        if sql.startswith('SELECT MAX(stamp) FROM recalls WHERE scope=? AND persona=?') and 'query=' not in sql and not conn.in_transaction:
                            read_barrier.wait(timeout=3)
                        return cursor
                yield Proxy()
        cold.db=raced_db
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs=[pool.submit(c.recall,S,'p',q) for c,q in ((first,'并发线索一'),(second,'并发线索二'))]
        states=sorted(job.result(timeout=8)['state'] for job in jobs)
    assert states==['cooldown','no_match']


async def test_cancelled_summary_keeps_original_query_budget(tmp_path):
    import asyncio
    cold,_=archive(tmp_path);e=engine();e.search_memories.side_effect=asyncio.CancelledError()
    result=cold.recall(S,'p','第一线索')
    with pytest.raises(asyncio.CancelledError):await summary_fallback(cold,e,S,'p','第一线索',result)
    out=cold.recall(S,'p','另一线索')
    assert out['state']=='cooldown' and not out['lookup_performed']

async def test_source_timeout_does_not_hide_next_record(tmp_path):
    cold,_=archive(tmp_path);cold.capture(S,'p','user','今天豆瓣酱倒多了，整盘咸了','fixture');e=engine()
    sources=e.get_memory_source.return_value
    e.search_memories.return_value=[NS(doc_id=6),NS(doc_id=7)]
    e.get_memory_source.side_effect=[TimeoutError(),sources]
    out=await summary_fallback(cold,e,S,'p','豆瓣酱放多',cold.recall(S,'p','豆瓣酱放多'))
    assert out['state']=='found_via_summary' and out['summary_lookup']=='unavailable_or_partial'
    assert not out['summary_hits'][0]['linked_original_found'] and out['summary_hits'][1]['linked_original_found']

def test_many_concurrent_recallers_only_consume_one_slot(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from astrbot_plugin_fish_capabilities.services.cold_memory import ColdMemory
    first,clock=archive(tmp_path)
    clients=[ColdMemory(first.root,clock=lambda:clock[0]) for _ in range(8)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        jobs=[pool.submit(c.recall,S,'p',f'并发线索{i}') for i,c in enumerate(clients)]
        states=[job.result(timeout=10)['state'] for job in jobs]
    assert states.count('no_match')==1 and states.count('cooldown')==7
    with first.db() as db:assert db.execute('SELECT COUNT(*) FROM recalls').fetchone()[0]==1
    clock[0]+=301
    assert first.recall(S,'p','后续新线索')['state']=='no_match'
