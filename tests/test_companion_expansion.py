import asyncio
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
import pytest
from astrbot_plugin_fish_capabilities.services.companion_learning import CompanionLearning
from astrbot_plugin_fish_capabilities.services.meme_semantic import MemeSemantic
from astrbot_plugin_fish_capabilities.services.group_digest import GroupDigest
from astrbot_plugin_fish_capabilities.services.history import GroupHistory
from astrbot_plugin_fish_capabilities.services.policy import Actor,CapabilityError
from astrbot_plugin_fish_capabilities.services.observability import usage_report,replay
from astrbot_plugin_fish_capabilities.services.capability_registry import authorize,FEATURE_ACCESS
from astrbot_plugin_fish_capabilities.services.reading_sources import public_cover
from astrbot_plugin_fish_capabilities.services.timetable import Timetable
from test_services import make_library
from test_astrbot_binding import plugin,Event


def test_pending_learning_is_scoped_reviewable_versioned_and_expires(tmp_path):
    now=[1000];store=CompanionLearning(tmp_path/'learning.db',lambda:now[0])
    item=store.save('private','observation','课程','推测最近课程比较忙',{'kind':'owner_statement','excerpt':'最近上课忙'})
    assert not store.recall('private','课程')
    with pytest.raises(CapabilityError):store.review('group',item['id'],'approved',1)
    store.review('private',item['id'],'approved',1)
    assert store.recall('private','课程') and not store.recall('group','课程')
    with pytest.raises(CapabilityError):store.review('private',item['id'],'rejected',1)
    changed=store.save('private','observation','课程','推测课程已经轻松了',{'kind':'owner_review'},approved=True,note_id=item['id'],revision=2)
    assert changed['revision']==3
    now[0]+=8*86400
    assert not store.recall('private','课程')
    assert store.list('private')[0]['expired']


def test_style_examples_have_provenance_and_do_not_invent_shared_experiences(tmp_path):
    store=CompanionLearning(tmp_path/'notes.db')
    store.save('private','style_negative','闲聊 分享','别每次先说“这一点我认”',{'kind':'owner_review'},approved=True)
    hint=store.style_hint('private','闲聊的时候分享视频')
    assert 'style_negative' in hint and '不复制经历' in hint
    assert not store.style_hint('another','闲聊')
    assert store.traces('private')[0]['ids']==[1]


def test_video_feedback_requires_explicit_current_evidence_and_deduplicates(tmp_path):
    store=CompanionLearning(tmp_path/'notes.db')
    with pytest.raises(CapabilityError):store.feedback('p','BV1234567890',1,'好看','很好看哦','没有说过')
    assert store.feedback('p','BV1234567890',1,'喜欢技术科普','这个讲得清楚','这个讲得清楚')['saved']
    assert store.feedback('p','BV1234567890',1,'same','这个讲得清楚','这个讲得清楚')['duplicate']
    assert not store.feedback_hints('other')


async def test_semantic_index_is_incremental_and_metadata_edit_invalidates_only_changed_asset(tmp_path):
    library=make_library(tmp_path/'memes')
    provider=NS(get_embedding=AsyncMock(return_value=[1,0,0]))
    search=MemeSemantic(tmp_path/'vectors.db',library,lambda:('same-model',provider))
    await search.index();calls=provider.get_embedding.await_count
    assert calls>=1
    await search.index();assert provider.get_embedding.await_count==calls
    result=await search.search('开心高兴')
    assert result['mode']=='semantic' and result['candidates']
    state=library.manageable();row=state['entries'][0]
    library.edit(row['id'],state['version'],description='新的含义',image_text='',usage_notes='',tags=[],category=row['category'],approved=True)
    assert search.status()['pending']==1
    await search.index();assert search.status()['pending']==0
    with pytest.raises(CapabilityError):library.edit(row['id'],state['version'],description='stale',image_text='',usage_notes='',tags=[],category=row['category'],approved=True)


async def test_unavailable_semantics_falls_back_to_existing_text_descriptions(tmp_path):
    library=make_library(tmp_path/'memes');search=MemeSemantic(tmp_path/'vectors.db',library,lambda:('',None))
    result=await search.search('happy')
    assert result['mode']=='text' and result['candidates']


def digest_fixture(tmp_path):
    root=tmp_path/'data';root.mkdir();source=root/'messages.db'
    with sqlite3.connect(source) as db:
        db.execute('CREATE TABLE messages(id INTEGER PRIMARY KEY,timestamp REAL,sender_id TEXT,sender_name TEXT,role TEXT,content TEXT,session_id TEXT,group_id TEXT)')
        db.execute('INSERT INTO messages VALUES(1,1000,?,?,?, ?,?,?)',('one','成员','user','讨论了课程','qq:GroupMessage:7','7'))
        db.execute('INSERT INTO messages VALUES(2,1001,?,?,?, ?,?,?)',('owner','主人','user','私聊秘密','qq:FriendMessage:owner',''))
    actor=Actor('owner','qq',True,True)
    return source,GroupHistory(source,root,['owner'],['qq:GroupMessage:7']),actor


async def test_incremental_group_digest_never_reads_private_and_reuses_cached_batches(tmp_path):
    source,reader,actor=digest_fixture(tmp_path);generate=AsyncMock(return_value='课程话题，来源ID 1。')
    digest=GroupDigest(tmp_path/'digest.db',generate,clock=lambda:2000)
    result=await digest.read(reader,actor,'7')
    assert result['new_messages_summarized']==1 and result['complete_history'] is False
    assert '私聊秘密' not in generate.await_args.args[0]
    assert (await digest.read(reader,actor,'7'))['new_messages_summarized']==0
    assert generate.await_count==1
    with sqlite3.connect(source) as db:
        db.execute("INSERT INTO messages VALUES(3,1500,'one','成员','user','后来解决了','qq:GroupMessage:7','7')")
    await digest.read(reader,actor,'7');assert generate.await_count==2
    with pytest.raises(CapabilityError):await digest.read(reader,Actor('other','qq',True,False),'7')


async def test_failed_group_summary_does_not_advance_cursor(tmp_path):
    source,reader,actor=digest_fixture(tmp_path)
    g=AsyncMock(side_effect=TimeoutError)
    digest=GroupDigest(tmp_path/'digest.db',g,clock=lambda:2000)
    with pytest.raises(TimeoutError):await digest.read(reader,actor,'7')
    g.side_effect=None;g.return_value='课程'
    assert (await digest.read(reader,actor,'7'))['new_messages_summarized']==1


async def test_soft_tasks_can_defer_once_and_explicit_reminders_ignore_intent_gate(tmp_path):
    now=[datetime.fromisoformat('2026-10-27T16:30:00+08:00').timestamp()]
    gate=AsyncMock(return_value={'decision':'defer','delay_seconds':60,'reason_code':'conversation_active'})
    browse=AsyncMock(return_value={'state':'read_without_recommendation'});remind=AsyncMock()
    clock=Timetable(tmp_path/'tasks.db',{'bili_scroll':browse,'reminder':remind},clock=lambda:now[0],gate=gate)
    clock.put('逛逛','bili_scroll','30 16 * * *');clock.put('喝水','reminder','30 16 * * *',{'text':'喝水'})
    await clock.tick();await clock.drain()
    assert not browse.called and remind.await_count==1
    gate.return_value={'decision':'run'};now[0]+=60
    await clock.tick();await clock.drain();await clock.tick();await clock.drain()
    assert browse.await_count==1 and remind.await_count==1


async def test_pause_removes_deferred_candidate_without_side_effect(tmp_path):
    now=[datetime.fromisoformat('2026-10-27T16:30:00+08:00').timestamp()]
    g=AsyncMock(return_value={'decision':'defer','delay_seconds':60});a=AsyncMock()
    t=Timetable(tmp_path/'tasks.db',{'bili_scroll':a},clock=lambda:now[0],gate=g)
    key=t.put('浏览','bili_scroll','30 16 * * *')['task_id']
    await t.tick();await t.drain();t.control(key,'pause');now[0]+=60
    await t.tick();await t.drain();assert not a.called


def test_unknown_usage_stays_unknown_and_context_chars_are_not_claimed_as_billing(tmp_path):
    p=tmp_path/'metrics.jsonl';p.write_text('\n'.join(json.dumps(r) for r in [
        {'at':1000,'stage':'request','history_chars':4000},
        {'at':1001,'stage':'reply','input_other':10,'input_cached':90,'output':5,'duration_ms':100}]))
    r=usage_report(p)
    assert r['currency_cost'] is None and r['stages']['request']['input_other'] is None
    assert r['stages']['reply']['cache_hit_ratio']==0.9


async def test_simulation_does_not_mutate_live_state_or_use_transports():
    intent=NS(last_decisions={'real':'unchanged'},bot_id='actual')
    result=await replay(intent,{'messages':[{'text':'给另一个人说话','target':'other'}]})
    assert result['should_reply'] is False and result['captured_actions']==[]
    assert intent.last_decisions=={'real':'unchanged'} and intent.bot_id=='actual'


def test_registry_rejects_unregistered_features_and_private_access_from_group():
    config={'enabled':True,'learning_enabled':True,'owners':['owner'],'allowed_group_sessions':['qq:GroupMessage:7']}
    with pytest.raises(CapabilityError):authorize(config,Actor('owner','qq',False,True,'7'),'learning')
    with pytest.raises(CapabilityError):authorize(config,Actor('owner','qq',True,True),'unknown')
    assert 'asr' in FEATURE_ACCESS and 'homophone' in FEATURE_ACCESS


@pytest.mark.parametrize('url',['https://evil.example/a.jpg','https://i0.hdslb.com@evil.example/a.jpg','file:///secret','http://127.0.0.1/a.jpg'])
def test_cover_never_uses_arbitrary_urls(url):
    assert public_cover(url)==''


async def test_group_impressions_require_review_and_do_not_cross_members(plugin):
    plugin.config.update(learning_enabled=True,group_learning_enabled=True)
    event=Event(private=False,sender='member',admin=False)
    event.get_message_str=lambda:'我最近在学点云渲染'
    response=json.loads(await plugin.group_observation_tool(event,'推测对图形学感兴趣','最近在学点云渲染'))
    assert response['state']=='pending'
    scope='qq_test:GroupMessage:77777'
    assert plugin.companion.hints(scope,'图形学',private=False,sender_id='member')[0]==''
    plugin.companion.learning.review(scope,response['id'],'approved',1)
    assert '主观印象' in plugin.companion.hints(scope,'其他话题',private=False,sender_id='member')[0]
    assert plugin.companion.hints(scope,'其他话题',private=False,sender_id='other')[0]==''


async def test_learning_tool_cannot_self_approve_without_explicit_owner_instruction(plugin):
    plugin.config.update(learning_enabled=True)
    event=Event();event.get_message_str=lambda:'这个话题很有意思'
    result=json.loads(await plugin.learning_tool(event,'propose',topic='话题',text='推测对这类内容感兴趣',evidence='话题很有意思'))
    assert result['state']=='pending'
    result=json.loads(await plugin.learning_tool(event,'review',note_id=result['id'],revision=1))
    assert result['ok'] is False
    event.get_message_str=lambda:'不要批准1'
    assert json.loads(await plugin.learning_tool(event,'review',note_id=1,revision=1))['ok'] is False


async def test_expanding_digest_window_backfills_older_unseen_messages(tmp_path):
    source,reader,actor=digest_fixture(tmp_path)
    with sqlite3.connect(source) as db:
        db.execute('UPDATE messages SET id=10 WHERE id=1')
        db.execute("INSERT INTO messages VALUES(3,-1000,'one','成员','user','更早的话题','qq:GroupMessage:7','7')")
    now=[4000];gen=AsyncMock(return_value='摘要')
    digest=GroupDigest(tmp_path/'digest.db',gen,lambda:now[0])
    assert (await digest.read(reader,actor,'7',hours=1))['new_messages_summarized']==1
    result=await digest.read(reader,actor,'7',hours=2)
    assert result['new_messages_summarized']==1
    raw=await reader.read_ids(actor,'7',[10,2])
    assert len(raw['messages'])==1 and raw['missing_ids']==[2]
