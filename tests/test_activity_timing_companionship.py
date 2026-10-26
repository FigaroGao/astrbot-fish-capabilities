import asyncio
import types
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from astrbot_plugin_fish_capabilities.services.timing import activity_timing, poll_delay
from astrbot_plugin_fish_capabilities.services.companionship import COMPANION_STYLE
from astrbot_plugin_fish_capabilities.services.private_initiative import Initiative
from test_astrbot_binding import plugin, Event
from test_bili_activity import make

CONFIG = {'initiative_start_hour':10,'initiative_end_hour':3,'initiative_interval_minutes':30,'background_poll_seconds':600}
HK = timezone(timedelta(hours=8))


def stamp(hour, minute=0, day=25):
    return datetime(2026,10,day,hour,minute,tzinfo=HK).timestamp()


@pytest.mark.parametrize('hour,minute,allowed',[(9,59,False),(10,0,True),(23,59,True),(0,0,True),(2,59,True),(3,0,False)])
def test_cross_midnight_window(hour,minute,allowed):
    assert activity_timing(CONFIG,stamp(hour,minute))['allowed'] is allowed


async def test_private_half_hour_gate_and_restart_do_not_burst(tmp_path):
    now=[stamp(10,29)]
    generate=AsyncMock(return_value='{"send":false,"message":""}')
    deliver=AsyncMock()
    p=Initiative(tmp_path/'private.db',generate,deliver,clock=lambda:now[0],config=CONFIG)
    p.offer('可以之后聊的话题')
    assert await p.tick()=='chose_silence'
    now[0]=stamp(10,30)
    assert await p.tick()=='already_judged'
    now[0]=stamp(10,59)
    assert await p.tick()=='chose_silence'
    other=Initiative(p.path,generate,deliver,clock=lambda:now[0],config=CONFIG)
    assert await other.tick()=='already_judged'
    assert generate.await_count==2 and deliver.await_count==0


async def test_midnight_does_not_reset_thinking_cooldown(tmp_path):
    now=[stamp(23,50)]
    g=AsyncMock(return_value='{"send":false}')
    p=Initiative(tmp_path/'private.db',g,AsyncMock(),clock=lambda:now[0],config=CONFIG)
    p.offer('有趣的事')
    assert await p.tick()=='chose_silence'
    now[0]=stamp(0,10,26)
    assert await p.tick()=='already_judged'
    now[0]=stamp(0,20,26)
    assert await p.tick()=='chose_silence'
    now[0]=stamp(3,0,26)
    assert await p.tick()=='quiet_hours' and g.await_count==2


async def test_dynamic_half_hour_and_new_context_required(tmp_path):
    a,b,r,g,n,t,c=make(tmp_path);a.config.update(CONFIG);g.return_value={'post':False}
    assert (await a.think())['state']=='chose_silence'
    t[0]+=20*60;c['at']=t[0]
    assert (await a.think())['state']=='already_thought'
    t[0]+=10*60;c['at']=t[0]
    assert (await a.think())['state']=='chose_silence'
    assert (await a.think())['state']=='no_new_context'
    assert g.await_count==2 and not b.sent


async def test_dynamic_after_midnight_and_three_am_stop(tmp_path):
    a,b,r,g,n,t,c=make(tmp_path);a.config.update(CONFIG);g.return_value={'post':False}
    t[0]=stamp(2,30,26);c['at']=t[0]
    assert (await a.think())['state']=='chose_silence'
    t[0]=stamp(3,0,26);c['at']=t[0]
    assert (await a.think())['state']=='quiet_hours' and g.await_count==1


async def test_live_checks_use_ten_minutes(tmp_path):
    a,b,r,g,n,t,c=make(tmp_path);a.config.update(CONFIG)
    await a.watch('7')
    assert (await a.poll())['state']=='checked'
    t[0]+=300
    assert (await a.poll())['state']=='cooldown'
    t[0]+=300
    assert (await a.poll())['state']=='checked'


def test_maintenance_checks_align_to_same_wall_clock_slots():
    assert poll_delay(CONFIG,stamp(10,3))==420
    assert poll_delay(CONFIG,stamp(10,10))==600
    assert poll_delay(CONFIG,stamp(10,19)+59)==1


async def test_companion_addendum_preserves_persona_and_not_duplicated(plugin):
    plugin.config.update(companionship_enabled=True,command_platform_ids=['qq_test'])
    req=types.SimpleNamespace(system_prompt='原有人格主体：原来的称呼和设定。')
    await plugin.support_companionship(Event(),req)
    await plugin.support_companionship(Event(),req)
    assert req.system_prompt.startswith('原有人格主体：原来的称呼和设定。\n')
    assert req.system_prompt.count(COMPANION_STYLE)==1
    outsider=types.SimpleNamespace(system_prompt='原文')
    await plugin.support_companionship(Event(sender='other'),outsider)
    assert outsider.system_prompt=='原文'


async def test_balance_loop_waits_for_shared_slot_before_api(plugin,monkeypatch):
    import astrbot_plugin_fish_capabilities.main as binding
    seen=[]
    async def sleep(delay):seen.append(delay);raise asyncio.CancelledError()
    plugin.config.update(CONFIG);plugin.quota=types.SimpleNamespace(get=AsyncMock())
    monkeypatch.setattr(binding,'poll_delay',lambda config:123)
    monkeypatch.setattr(binding.asyncio,'sleep',sleep)
    with pytest.raises(asyncio.CancelledError):await plugin.sample_balance()
    assert seen==[123] and plugin.quota.get.await_count==0


@pytest.mark.parametrize('kind,expected',[('private_initiative',True),('bili_dynamic_draft',True),('bili_public_review',False)])
async def test_background_style_only_changes_drafting_not_review(plugin,kind,expected):
    plugin.config['companionship_enabled']=True
    provider=types.SimpleNamespace(provider_config={},text_chat=AsyncMock(return_value=types.SimpleNamespace(usage=None)))
    plugin.context=types.SimpleNamespace(get_provider_by_id=lambda key:provider)
    await plugin.bounded_generate('test-provider',prompt='资料',system_prompt='原有后台主体',max_tokens=100,timeout=5,kind=kind)
    system=provider.text_chat.call_args.kwargs['system_prompt']
    assert system.startswith('原有后台主体') and (COMPANION_STYLE in system) is expected
