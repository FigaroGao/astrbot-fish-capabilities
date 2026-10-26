import json
import types
from unittest.mock import AsyncMock
from datetime import datetime,timedelta,timezone

from astrbot_plugin_fish_capabilities.services.group_quiet import GroupQuiet
from astrbot_plugin_fish_capabilities.services.private_initiative import Initiative
from astrbot_plugin_fish_capabilities.services.intent_runtime import IntentRuntime
from test_intent_runtime import runtime, Event, Gcp, consume
from test_astrbot_binding import plugin
from test_group_quiet import QuietEvent


async def test_private_no_daily_cap_or_three_hour_gap_but_half_hour_gate(tmp_path):
    now=[datetime(2026,10,26,10,tzinfo=timezone(timedelta(hours=8))).timestamp()]
    g=AsyncMock(return_value='{"send":true,"message":"想起件有趣的事。"}')
    send=AsyncMock()
    config={'initiative_start_hour':10,'initiative_end_hour':3,'initiative_interval_minutes':30,
            'private_initiative_daily_limit':0,'private_initiative_cooldown_seconds':0}
    p=Initiative(tmp_path/'private.db',g,send,clock=lambda:now[0],config=config)
    p.offer('新的话题')
    assert await p.tick()=='sent'
    now[0]+=16*60
    assert await p.tick()=='already_judged'
    now[0]+=14*60
    assert await p.tick()=='sent'
    now[0]+=30*60
    assert await p.tick()=='sent' and send.await_count==3
    p.observe('先别找我');now[0]+=30*60
    assert await p.tick()=='busy' and send.await_count==3


async def test_group_automatic_stop_uses_same_persistent_quiet(runtime,tmp_path):
    scope=Event.unified_msg_origin
    quiet=GroupQuiet(tmp_path/'quiet.json',clock=runtime.clock)
    runtime.cap.group_quiet=quiet;runtime.cap.config['intent_self_pause_enabled']=True
    runtime.judge=AsyncMock(return_value='stop_conversation')
    old=Event();quiet.mark(old);g=Gcp()
    assert await consume(runtime,g,Event('这段聊完了'))==[]
    assert quiet.muted(scope) and quiet.suppress(old) and g.calls==0
    assert await consume(runtime,g,Event('又@你了',True))==[]
    restored=GroupQuiet(quiet.path,clock=runtime.clock)
    assert restored.muted(scope)
    runtime.test_now[0]+=121
    assert not quiet.muted(scope) and quiet.suppress(old)
    assert await consume(runtime,g,Event('新话题',True))


async def test_normal_non_direct_reply_with_real_silencer_does_not_shadow_float(runtime,tmp_path):
    runtime.cap.group_quiet=GroupQuiet(tmp_path/'quiet.json',clock=runtime.clock)
    assert await consume(runtime,Gcp(),Event())==['one whole response']


async def test_false_verdict_is_not_a_two_minute_pause(runtime,tmp_path):
    runtime.cap.group_quiet=GroupQuiet(tmp_path/'quiet.json',clock=runtime.clock)
    runtime.judge=AsyncMock(return_value=False)
    assert await consume(runtime,Gcp(),Event())==[]
    assert not runtime.cap.group_quiet.state


async def test_stale_stop_verdict_cannot_silence_new_conversation(runtime,tmp_path):
    runtime.cap.group_quiet=GroupQuiet(tmp_path/'quiet.json',clock=runtime.clock)
    runtime.cap.config['intent_self_pause_enabled']=True
    async def judge(scope,rows):
        runtime.observe(Event('新的消息'))
        return 'stop_conversation'
    runtime.judge=judge
    assert await consume(runtime,Gcp(),Event())==[]
    assert not runtime.cap.group_quiet.state


async def test_real_judge_requires_valid_stop_and_prior_bot_participation(runtime):
    runtime.cap.config['intent_self_pause_enabled']=True;runtime.bot_id='bot'
    result={'should_reply':False,'addressed_to_bot':True,'stop_conversation':True,'reason':'话题已结束'}
    api=AsyncMock(return_value=types.SimpleNamespace(completion_text=json.dumps(result)))
    runtime.cap.context=types.SimpleNamespace(llm_generate=api)
    assert await IntentRuntime.judge(runtime,'scope',[]) is False
    assert await IntentRuntime.judge(runtime,'scope',[{'role':'assistant'}])=='stop_conversation'
    result['should_reply']=True
    api.return_value=types.SimpleNamespace(completion_text=json.dumps(result))
    assert await IntentRuntime.judge(runtime,'scope',[{'role':'assistant'}]) is False


async def test_group_pause_tool_stops_without_ack_and_owner_can_resume(plugin):
    plugin.config.update(intent_self_pause_enabled=True,command_platform_ids=['qq_test'])
    e=QuietEvent('小鲸自己决定退场');e.get_self_id=lambda:'bot'
    value=json.loads(await plugin.group_pause_tool(e))
    assert value['paused'] and e.stopped and not e.sent
    scope=e.unified_msg_origin;until=plugin.group_quiet.state[scope]['until']
    await plugin.group_pause_tool(e)
    assert plugin.group_quiet.state[scope]['until']==until
    resume=QuietEvent('/开口')
    assert await plugin.group_quiet_before_wake(resume,{'admins_id':['10001']})
    assert not plugin.group_quiet.muted(scope)


async def test_group_pause_tool_cannot_pause_private_or_other_group(plugin):
    from test_astrbot_binding import Event as BasicEvent
    plugin.config.update(intent_self_pause_enabled=True,command_platform_ids=['qq_test'])
    assert not json.loads(await plugin.group_pause_tool(BasicEvent()))['ok']
    plugin.config['allowed_group_sessions']=[]
    e=QuietEvent();e.get_self_id=lambda:'bot'
    assert not json.loads(await plugin.group_pause_tool(e))['ok'] and not plugin.group_quiet.state


async def test_owner_resume_during_judgment_is_not_overridden(runtime,tmp_path):
    quiet=GroupQuiet(tmp_path/'quiet.json',clock=runtime.clock)
    runtime.cap.group_quiet=quiet;runtime.cap.config['intent_self_pause_enabled']=True
    e=Event();quiet.mark(e)
    async def judge(scope,rows):
        quiet.set(scope,0)
        return 'stop_conversation'
    runtime.judge=judge
    assert await consume(runtime,Gcp(),e)==[]
    assert not quiet.muted(e.unified_msg_origin)


async def test_old_tool_call_cannot_undo_owner_resume(plugin):
    plugin.config.update(intent_self_pause_enabled=True,command_platform_ids=['qq_test'])
    e=QuietEvent();e.get_self_id=lambda:'bot';plugin.group_quiet.mark(e)
    plugin.group_quiet.set(e.unified_msg_origin,0)
    assert not json.loads(await plugin.group_pause_tool(e))['ok']
    assert not plugin.group_quiet.muted(e.unified_msg_origin)
