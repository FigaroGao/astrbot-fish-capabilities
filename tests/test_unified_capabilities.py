import asyncio
import hashlib
import json
import sqlite3
from datetime import datetime
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
import pytest
from astrbot_plugin_fish_capabilities.services.timetable import Timetable,HK
from astrbot_plugin_fish_capabilities.services.activity_timeline import ActivityTimeline
from astrbot_plugin_fish_capabilities.services.memory_editor import MemoryEditor
from astrbot_plugin_fish_capabilities.services.policy import CapabilityError
from astrbot_plugin_fish_capabilities.services.bili_mentions import OwnerMentions
from astrbot_plugin_fish_capabilities.services.bilibili import BiliReader
from test_services import BiliFake,BV
from test_astrbot_binding import plugin
from test_bili_comments import Posting
from astrbot_plugin_fish_capabilities.services.bili_comments import BiliComments


def board(tmp_path,when='2026-10-27T16:30:00+08:00'):
    clock=[datetime.fromisoformat(when).timestamp()]
    action=AsyncMock()
    return Timetable(tmp_path/'tasks.db',{'reminder':action},clock=lambda:clock[0]),action,clock

async def test_schedule_survives_restart_and_never_duplicates(tmp_path):
    t,a,c=board(tmp_path)
    ident=t.put('下午提醒','reminder','30 16 * * *',{'text':'喝水'})['task_id']
    await t.tick();await t.drain();await t.tick();await t.drain()
    assert a.await_count==1
    other=Timetable(t.path,t.actions,clock=lambda:c[0]);await other.tick();await other.drain()
    assert a.await_count==1
    assert other.list()['tasks'][0]['id']==ident
    assert other.list()['tasks'][0]['last_run'][1]=='completed'

async def test_pause_resume_cancel_and_update(tmp_path):
    t,a,c=board(tmp_path);ident=t.put('提醒','reminder','30 16 * * *',{'text':'喝水'})['task_id']
    t.control(ident,'pause');await t.tick();assert not a.called
    t.control(ident,'resume');await t.tick();await t.drain();assert a.await_count==1
    t.put('修改提醒','reminder','31 16 * * *',{'text':'看书'},ident)
    c[0]+=60;await t.tick();await t.drain();assert a.await_args.kwargs['text']=='看书'
    t.control(ident,'cancel');assert t.list()['tasks']==[]

async def test_missed_time_no_backfill_and_one_shot(tmp_path):
    t,a,c=board(tmp_path,'2026-10-27T16:32:00+08:00')
    t.put('错过','reminder','30 16 * * *',{'text':'不补发'})
    once=t.put('一次','reminder','at:2026-10-27T16:33:00+08:00',{'text':'一次'})
    await t.tick();assert not a.called
    c[0]+=60;await t.tick();await t.drain();assert a.await_count==1
    c[0]+=60;await t.tick();await t.drain();assert a.await_count==1

@pytest.mark.parametrize('action,timing,args',[('shell','* * * * *',{}),('reminder','bad',{'text':'x'}),('reminder','* * * * *',{}),('reminder','* * * * *',{'shell':'x'}),('reminder','at:2020-01-01T00:00:00',{'text':'x'})])
def test_invalid_tasks_fail_closed(tmp_path,action,timing,args):
    t,_,_=board(tmp_path)
    with pytest.raises(CapabilityError):t.put('bad',action,timing,args)
    assert t.list()['tasks']==[]

async def test_long_job_cannot_block_other_minute_or_repeat(tmp_path):
    t,a,c=board(tmp_path);started=asyncio.Event();release=asyncio.Event()
    async def slow(*_,**__):started.set();await release.wait()
    t.actions['slow']=slow;t.put('slow','slow','* * * * *')
    await t.tick();await started.wait()
    t.put('remind','reminder','31 16 * * *',{'text':'hello'})
    c[0]+=60;await t.tick();await asyncio.sleep(.01)
    assert a.await_count==1
    t.stop();await t.drain()
    with t.db() as db:states=[r[0] for r in db.execute('SELECT state FROM executions')]
    assert 'overlap_skipped' in states and 'interrupted' in states

async def test_pause_cancels_inflight_future_steps(tmp_path):
    t,a,c=board(tmp_path);start=asyncio.Event()
    async def job(*_,**__):start.set();await asyncio.sleep(100);await a()
    t.actions['slow']=job;i=t.put('slow','slow','* * * * *')['task_id']
    await t.tick();await start.wait();t.control(i,'pause');await t.drain();assert not a.called

async def test_failed_task_reserved_no_retry(tmp_path):
    t,a,c=board(tmp_path);a.side_effect=TimeoutError('private!')
    t.put('提醒','reminder','* * * * *',{'text':'x'})
    await t.tick();await t.drain();await t.tick();await t.drain();assert a.await_count==1
    assert 'private!' not in json.dumps(t.list())


def test_timeline_retention_provenance_and_literal_search(tmp_path):
    clock=[1.0];timeline=ActivityTimeline(tmp_path/'timeline.db',clock=lambda:clock[0])
    timeline.add('bili','one','视频100%很好',state='submitted')
    timeline.add('bili','one','不得重复')
    assert len(timeline.search('%')['events'])==1
    assert timeline.search('不存在')['events']==[]
    clock[0]+=31*86400;timeline.add('qq','new','你好')
    assert len(timeline.search()['events'])==1

async def test_memory_scope_hash_evidence_and_rebuild(tmp_path):
    editor=MemoryEditor(tmp_path/'edits.db')
    row={'text':'旧事实','metadata':{'session_id':'qq:FriendMessage:owner','persona_id':'fish','key_facts':['旧事实']}}
    result=NS(doc_id=1)
    engine=NS(search_memories=AsyncMock(return_value=[result]),get_memory_record=AsyncMock(return_value=row),get_memory_source=AsyncMock(return_value=[]),replace_memory=AsyncMock(return_value=2))
    scope='qq:FriendMessage:owner';found=await editor.search(engine,scope,'fish','事实')
    assert found['memories'][0]['id']==1
    version=found['memories'][0]['version']
    for args in [('wrong','fish',version,'这条已经改了','这条已经改了'),(scope,'fish','stale','这条已经改了','这条已经改了'),(scope,'fish',version,'瞎编的依据','这条已经改了')]:
        with pytest.raises(CapabilityError):await editor.correct(engine,args[0],args[1],1,args[2],'新事实','更正错误',args[3],args[4])
    assert not engine.replace_memory.called
    out=await editor.correct(engine,scope,'fish',1,version,'新事实','更正错误','这条已经改了','这条已经改了')
    assert out['new_id']==2
    assert engine.replace_memory.await_args.kwargs['metadata']['key_facts']==['新事实']
    with sqlite3.connect(editor.path) as db:
        saved=db.execute('SELECT before,state FROM edits').fetchone()
    assert '旧事实' in json.loads(saved[0])['record']['text'] and saved[1]=='completed'

async def test_typed_visual_description_allow_comment_without_subtitles(tmp_path):
    class Backend(BiliFake):
        async def read(self,bv):
            raw=await super().read(bv);raw['segments']=[];raw['info']['desc']='作者介绍海洋生物';return raw
    reader=BiliReader(tmp_path/'b.db',Backend())
    async def vision(*_):return {'visual_content_seen':True,'visual_summary':'有鲸鱼画面，小字无法辨认','preview_timestamps':[2,5]}
    reader.visual_reader=vision;p=await reader.read(BV)
    assert {e['kind'] for e in p['evidence']}=={'description','sampled_visual'}
    reviewer=NS(gate=AsyncMock());writer=BiliComments(reader,{'bili_account_id':'42','bili_comment_enabled':True},Posting());writer.reviewer=reviewer
    await writer.post(p['reading_id'],'鲸鱼好可爱。',[BV+':visual'])
    material=reviewer.gate.await_args.args[3]
    assert len(material['evidence'])==1 and material['evidence'][0]['kind']=='sampled_visual'
    assert p['subtitle_coverage']==0

async def test_failed_visual_never_issues_visual_source(tmp_path):
    reader=BiliReader(tmp_path/'b.db',BiliFake(empty=True))
    async def vision(*_):return {'visual_content_seen':False,'visual_summary':'没有看见'}
    reader.visual_reader=vision;p=await reader.read(BV)
    assert not p['evidence']

async def make_mentions(tmp_path):
    reader=BiliReader(tmp_path/'b.db',BiliFake())
    config={'enabled':True,'bili_enabled':True,'bili_activity_enabled':True,'bili_public_review_enabled':True,'bili_owner_uid':'7','bili_account_id':'42','bili_owner_at_enabled':True}
    backend=NS(messages=AsyncMock(return_value={'items':[]}))
    activity=NS(reader=reader,config=config,account=lambda:'42',identity=AsyncMock(),backend=backend,lock=asyncio.Lock())
    comments=NS(post=AsyncMock(),reviewer=NS());gen=AsyncMock(return_value=json.dumps({'comment':'好看','evidence_ids':[BV+':s0']}))
    timeline=ActivityTimeline(tmp_path/'timeline.db')
    mentions=OwnerMentions(activity,comments,gen,timeline,clock=lambda:1000)
    mentions.resolve=AsyncMock(return_value=BV)
    return mentions,backend,comments,gen


def notice(owner=7,recipient=42,stamp=1000,kind='reply',business=1):
    return {'id':123,'at_time':stamp,'user':{'mid':owner},'item':{'subject_id':456,'type':kind,'business_id':business,'at_details':[{'mid':recipient}]}}

@pytest.mark.parametrize('value',[notice(owner=8),notice(recipient=99),notice(stamp=1),notice(kind='dynamic'),notice(business=2)])
async def test_mentions_reject_third_parties_old_and_wrong_targets(tmp_path,value):
    m,b,c,g=await make_mentions(tmp_path);b.messages.return_value={'items':[value]}
    assert (await m.check())['state']=='no_new_owner_mentions'
    assert not c.post.called and not g.called

async def test_owner_mention_reads_video_comments_once_and_uses_existing_gate(tmp_path):
    m,b,c,g=await make_mentions(tmp_path);b.messages.return_value={'items':[notice()]}
    assert (await m.check())['state']=='comment_attempted'
    assert (await m.check())['state']=='no_new_owner_mentions'
    assert c.post.await_count==1 and m.resolve.await_count==1
    assert 'comments' in g.await_args.args[0]

async def test_uncertain_comment_never_retried(tmp_path):
    m,b,c,g=await make_mentions(tmp_path);b.messages.return_value={'items':[notice()]};c.post.side_effect=TimeoutError('private!')
    assert (await m.check())['error_type']=='TimeoutError'
    await m.check();assert c.post.await_count==1


async def test_historical_memory_reframe_requires_independent_evidence_review(tmp_path):
    review=AsyncMock(return_value=False)
    editor=MemoryEditor(tmp_path/'history.db',review)
    row={'text':'2026-10-23 当时历史每轮全部重读','metadata':{'session_id':'private','persona_id':'fish'}}
    engine=NS(get_memory_record=AsyncMock(return_value=row),get_memory_source=AsyncMock(return_value=[]),replace_memory=AsyncMock(return_value=2))
    version=hashlib.sha256(row['text'].encode()).hexdigest()
    args=(engine,'private','fish',1,version,'2026-10-23讨论过历史上下文开销','临时状态改为历史','当时历史每轮全部重读','我回来啦')
    with pytest.raises(CapabilityError):await editor.correct(*args)
    assert not engine.replace_memory.called
    review.return_value=True
    assert (await editor.correct(*args))['corrected']
    assert review.await_args.args[0]['historical_only']

async def test_mentions_require_review_even_if_owner_requested(tmp_path):
    m,b,c,g=await make_mentions(tmp_path);c.reviewer=None;b.messages.return_value={'items':[notice()]}
    assert (await m.check())['state']=='review_unavailable'
    assert not c.post.called

async def test_owner_tools_never_exposed_to_group_or_other_private_users(plugin):
    from test_astrbot_binding import Event
    plugin.config.update(timetable_enabled=True,timeline_enabled=True,memory_edit_enabled=True)
    for event in (Event(private=False),Event(sender='other',admin=False)):
        assert json.loads(await plugin.tasks_tool(event))['ok'] is False
        assert json.loads(await plugin.timeline_tool(event))['ok'] is False
        assert json.loads(await plugin.memory_edit_tool(event,'search',query='秘密'))['ok'] is False


async def test_expired_one_shot_does_not_backfill_after_outage(tmp_path):
    t,a,c=board(tmp_path)
    t.put('一次','reminder','at:2026-10-27T16:31:00+08:00',{'text':'不要补发'})
    c[0]+=180
    await t.tick();await t.drain()
    assert not a.called and t.list()['tasks'][0]['next_at'] is None


async def test_disabled_timeline_does_not_collect_manual_reads(plugin):
    plugin.config['timeline_enabled']=False
    plugin.record_video_activity({'reading_id':'synthetic','title':'no collection','bvid':BV})
    assert plugin.timeline.search()['events']==[]


def test_shared_timeline_in_bili_drafts_and_review_never_forges_owner_activity(tmp_path):
    from astrbot_plugin_fish_capabilities.services.bili_review import PublicReview
    reader=BiliReader(tmp_path/'b.db',BiliFake())
    review=PublicReview(reader,tmp_path,AsyncMock(),AsyncMock(),{})
    review.timeline=ActivityTimeline(tmp_path/'shared.db')
    review.timeline.add('qq_private_received','one','我去上课了')
    review.timeline.add('bili_comment','two','一条公开评论',state='submitted')
    context=review.context()
    assert len(context['private_activity_timeline'])==2
    assert 'at' not in context
    review.timeline=None
    assert review.context()=={}
