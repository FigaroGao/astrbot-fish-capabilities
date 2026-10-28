import json,types
from datetime import datetime,timezone,timedelta
from unittest.mock import AsyncMock
import pytest
from test_bili_activity import make
from test_astrbot_binding import plugin
from test_services import BiliFake,BV
from astrbot_plugin_fish_capabilities.services.bilibili import BiliReader
from astrbot_plugin_fish_capabilities.services.bili_duty import BiliDuty
from astrbot_plugin_fish_capabilities.services.companionship import scene_hint


async def test_self_directed_can_read_more_than_three_and_stop(tmp_path):
    r=BiliReader(tmp_path/'b.db',BiliFake());r.browse=AsyncMock(return_value={'videos':[{'bvid':'BV'+str(i).zfill(10)} for i in range(6)]})
    r.read=AsyncMock(side_effect=lambda bv,**kw:dict(bvid=bv,title=bv))
    g=AsyncMock(return_value=json.dumps({'bvids':['BV'+str(i).zfill(10) for i in range(5)],'browse_more':False}))
    duty=BiliDuty(r,types.SimpleNamespace(),{'bili_scroll_unlimited_enabled':True},g,AsyncMock())
    packets,reason=await duty.self_directed('')
    assert len(packets)==5 and r.read.await_count==5 and g.await_count==1


async def test_self_directed_can_continue_new_batch_without_duplicate_reads(tmp_path):
    r=BiliReader(tmp_path/'b.db',BiliFake());r.browse=AsyncMock(side_effect=[{'videos':[{'bvid':'BV0000000001'}]},{'videos':[{'bvid':'BV0000000001'},{'bvid':'BV0000000002'}]}])
    r.read=AsyncMock(side_effect=lambda bv,**kw:dict(bvid=bv,title=bv))
    g=AsyncMock(side_effect=[json.dumps({'bvids':['BV0000000001'],'browse_more':True}),json.dumps({'bvids':['BV0000000002'],'browse_more':False})])
    duty=BiliDuty(r,types.SimpleNamespace(),{},g,AsyncMock())
    packets,_=await duty.self_directed('');assert [p['bvid'] for p in packets]==['BV0000000001','BV0000000002']
    assert r.read.await_count==2


async def test_self_directed_failure_stops_instead_of_retrying_other_counts(tmp_path):
    r=BiliReader(tmp_path/'b.db',BiliFake());r.browse=AsyncMock(return_value={'videos':[{'bvid':BV}]});r.read=AsyncMock(side_effect=RuntimeError())
    g=AsyncMock(return_value=json.dumps({'bvids':[BV],'browse_more':True}))
    packets,reason=await BiliDuty(r,types.SimpleNamespace(),{},g,AsyncMock()).self_directed('')
    assert not packets and reason=='read_failed_stop' and r.read.await_count==1


async def test_dynamic_midnight_no_longer_fires_and_clock_is_current(tmp_path):
    a,b,r,g,n,t,c=make(tmp_path);a.config.update(bili_dynamic_daytime_enabled=True,initiative_start_hour=10,initiative_end_hour=3)
    hk=timezone(timedelta(hours=8));t[0]=datetime(2026,10,28,0,tzinfo=hk).timestamp();c['at']=t[0]
    assert (await a.think())['state']=='dynamic_quiet_hours';g.assert_not_called()
    t[0]=datetime(2026,10,28,22,tzinfo=hk).timestamp();c['at']=t[0]
    await a.think();assert g.await_count==1 and '22:00' in g.call_args.args[0]['current_hong_kong_time']


async def test_dynamic_old_night_context_is_not_reused_in_daytime(tmp_path):
    a,b,r,g,n,t,c=make(tmp_path);a.config['bili_dynamic_daytime_enabled']=True
    t[0]+=12*3600
    assert (await a.think())['state']=='context_stale';g.assert_not_called()


def test_casual_pain_is_not_turned_into_emotional_mirror_or_medical_checklist():
    assert '不在求诊断' not in scene_hint('今天刷什么视频')
    assert '抽象渲染' in scene_hint('行，刚刚手机砸脸了，好疼')
    assert scene_hint('手机砸脸，出血不止怎么办')==''


async def test_real_request_hook_adds_scene_hint_once_without_rewriting_persona(plugin):
    from test_astrbot_binding import Event
    plugin.config.update(companionship_enabled=True,command_platform_ids=['qq_test'])
    event=Event();event.get_message_str=lambda:'行，刚刚手机砸脸了，好疼'
    req=types.SimpleNamespace(system_prompt='original persona')
    await plugin.support_companionship(event,req);await plugin.support_companionship(event,req)
    assert req.system_prompt.startswith('original persona') and req.system_prompt.count('[本轮场景：')==1


async def test_rest_boundary_is_a_small_deduplicated_addendum(plugin):
    from test_astrbot_binding import Event
    from astrbot_plugin_fish_capabilities.services.companionship import REST_BOUNDARY
    plugin.config.update(companionship_enabled=True,command_platform_ids=['qq_test'])
    event=Event();event.get_message_str=lambda:'睡不着，我想聊聊视频'
    req=types.SimpleNamespace(system_prompt='unchanged persona')
    await plugin.support_companionship(event,req);await plugin.support_companionship(event,req)
    assert req.system_prompt.startswith('unchanged persona') and req.system_prompt.count(REST_BOUNDARY)==1
    assert '不是替主人结束当前对话的权限' in req.system_prompt
