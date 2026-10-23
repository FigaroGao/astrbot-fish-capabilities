import asyncio
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
import pytest
from astrbot_plugin_fish_capabilities.services.intent_runtime import IntentRuntime
from astrbot_plugin_fish_capabilities.services.policy import Ledger


class Event:
    unified_msg_origin='qq:GroupMessage:g'
    call_llm=False
    def __init__(self,text='有个尚未解决的问题',direct=False):
        self.extras={};self.text=text;self.is_at_or_wake_command=direct
    def get_extra(self,key):return self.extras.get(key)
    def set_extra(self,key,value):self.extras[key]=value
    def get_self_id(self):return 'bot'
    def get_sender_id(self):return 'member'
    def get_message_str(self):return self.text
    def get_messages(self):return []
    def is_private_chat(self):return False


@pytest.fixture
def runtime(tmp_path):
    cap=NS(config={'enabled':True,'intent_enabled':True,'allowed_group_sessions':[Event.unified_msg_origin],
                   'intent_quiet_seconds':0,'intent_cooldown_seconds':180},
           ledger=Ledger(tmp_path/'budget.db'))
    now=[1000.0]
    r=IntentRuntime(cap,clock=lambda:now[0]);r.test_now=now
    r.judge=AsyncMock(return_value=True)
    return r


class Gcp:
    def __init__(self):self.calls=0
    async def _process_message(self,event):
        self.calls+=1
        yield 'one whole response'


async def consume(r,gcp,event):
    return [x async for x in r.run(gcp,event)]


async def test_direct_bypasses_judge_and_spontaneous_cooldown(runtime):
    g=Gcp()
    assert await consume(runtime,g,Event(direct=True))
    assert not await consume(runtime,g,Event())
    runtime.judge.assert_not_awaited()
    assert await consume(runtime,g,Event(direct=True))


async def test_lock_covers_generation_and_all_segments_and_burst_merges(runtime):
    g=Gcp();first=Event(direct=True);started=asyncio.Event();finish=asyncio.Event()
    async def onion():
        async for _ in runtime.run(g,first):
            started.set()
            # Simulates nested Agent/tools/respond stages completing all segments.
            await finish.wait()
    task=asyncio.create_task(onion());await started.wait()
    for i in range(20):
        e=Event(str(i));runtime.observe(e)
        assert await consume(runtime,g,e)==[]
    assert runtime.locks[first.unified_msg_origin].locked() and g.calls==1
    finish.set();await task
    assert not runtime.locks[first.unified_msg_origin].locked()
    assert len(runtime.records[first.unified_msg_origin])==20
    assert not await consume(runtime,g,Event())


async def test_only_latest_direct_request_waits_for_current_turn(runtime):
    g=Gcp();scope=Event.unified_msg_origin
    await runtime.locks[scope].acquire()
    a=asyncio.create_task(consume(runtime,g,Event('first',True)))
    await asyncio.sleep(0)
    b=asyncio.create_task(consume(runtime,g,Event('second',True)))
    await asyncio.sleep(0);runtime.locks[scope].release()
    assert await a==[] and await b and g.calls==1


async def test_stale_model_result_is_discarded(runtime):
    async def judge(scope,rows):
        runtime.observe(Event('new topic'))
        return True
    runtime.judge=judge;g=Gcp()
    assert await consume(runtime,g,Event())==[] and g.calls==0


async def test_judge_failure_stays_silent_and_does_not_fallback(runtime):
    runtime.judge=AsyncMock(side_effect=TimeoutError)
    e=Event();g=Gcp()
    assert await consume(runtime,g,e)==[] and e.call_llm and g.calls==0


async def test_hourly_budget_survives_new_runtime(runtime):
    runtime.cap.config.update(intent_cooldown_seconds=0,intent_hourly_limit=1)
    assert await consume(runtime,Gcp(),Event())
    runtime.test_now[0]+=60
    restarted=IntentRuntime(runtime.cap,clock=runtime.clock)
    assert not restarted.eligible(Event.unified_msg_origin,runtime.clock())


@pytest.mark.parametrize('raw',['{}','{"should_reply":"true","addressed_to_bot":true,"reason":"x"}',
    '{"should_reply":true,"addressed_to_bot":true}', 'not json'])
async def test_real_parser_rejects_invalid_verdict(runtime,raw):
    runtime.cap.context=NS(llm_generate=AsyncMock(return_value=NS(completion_text=raw)))
    runtime.bot_id='bot'
    try:verdict=await IntentRuntime.judge(runtime,'scope',[])
    except ValueError:verdict=False
    assert verdict is False


async def test_reply_to_someone_else_is_silent_without_model(runtime):
    Reply=type('Reply',(),{'sender_id':'other-member'})
    e=Event();e.get_messages=lambda:[Reply()]
    assert not await consume(runtime,Gcp(),e)
    runtime.judge.assert_not_awaited()


async def test_cancelled_generation_releases_lock_and_charges_uncertain_turn(runtime):
    scope=Event.unified_msg_origin;g=Gcp();agen=runtime.run(g,Event(direct=True))
    assert await anext(agen)
    await agen.aclose()
    assert not runtime.locks[scope].locked()
    assert not runtime.eligible(scope,runtime.clock())


async def test_runtime_hot_reload_keeps_synchronization(runtime):
    runtime.cap.context=NS()
    first=IntentRuntime(runtime.cap,clock=runtime.clock)
    second=IntentRuntime(runtime.cap,clock=runtime.clock)
    assert first.locks is second.locks and first.records is second.records


async def test_real_onion_scheduler_holds_lock_through_respond(runtime):
    # Import just the installed-style recursion contract without AstrBot dependencies.
    async def process_stages(stages,i=0):
        if i>=len(stages):return
        value=stages[i]()
        if hasattr(value,'__aiter__'):
            async for _ in value:await process_stages(stages,i+1)
        else:await value
    seen=[];g=Gcp();event=Event(direct=True)
    async def star_stage():
        async for _ in runtime.run(g,event):yield
    async def respond_stage():
        for segment in range(3):
            assert runtime.locks[event.unified_msg_origin].locked()
            assert not await consume(runtime,g,Event('during segment '+str(segment)))
            seen.append(segment)
    await process_stages([star_stage,respond_stage])
    assert seen==[0,1,2] and g.calls==1
