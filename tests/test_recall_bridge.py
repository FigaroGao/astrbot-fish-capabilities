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
