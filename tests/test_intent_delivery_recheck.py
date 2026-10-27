import json
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
import pytest
from test_intent_runtime import Event, runtime
from astrbot_plugin_fish_capabilities.services.intent_runtime import IntentRuntime
from astrbot_plugin_fish_capabilities.services.group_quiet import install_send_guard


async def test_identity_judgment_receives_primary_name_and_nonexclusive_names(runtime):
    runtime.cap.config.update(bot_primary_name='小鲸',bot_nonexclusive_names=['大肥鱼','小鲸鱼'])
    reply={'should_reply':False,'addressed_to_bot':False,'reason':'谈论其他机器人'}
    runtime.cap.context=NS(llm_generate=AsyncMock(return_value=NS(completion_text=json.dumps(reply))))
    runtime.bot_id='bot'
    assert await IntentRuntime.judge(runtime,'scope',[{'role':'user','text':'隔壁群的大肥鱼又刷屏了'}]) is False
    args=runtime.cap.context.llm_generate.call_args.kwargs
    assert json.loads(args['prompt'])['bot_identity']=={'primary_name':'小鲸','nonexclusive_names':['大肥鱼','小鲸鱼']}
    assert '不能单凭' in args['system_prompt']


@pytest.mark.parametrize('text',['大肥鱼','蓝色大肥鱼，过来','小鲸鱼今天好安静','别人的小鲸在B站发评论了'])
def test_textual_names_do_not_bypass_address_judgment(runtime,text):
    assert runtime.direct(Event(text)) is False


def test_real_at_or_quote_still_identifies_current_account_despite_old_nickname(runtime):
    for kind,field in [('At','qq'),('Reply','sender_id')]:
        part=type(kind,(),{field:'bot'})()
        event=Event('大肥鱼，听得到吗？');event.get_messages=lambda:[part]
        assert runtime.direct(event) is True


def pending(runtime):
    event=Event(direct=True)
    runtime.observe(event)
    event.set_extra('fish_intent_approved',True)
    event.set_extra('fish_intent_generation_revision',runtime.revisions[event.unified_msg_origin])
    return event


async def test_new_direct_request_cancels_old_unsent_draft_without_extra_judge(runtime):
    event=pending(runtime)
    runtime.observe(Event('新的明确问题',direct=True))
    assert await runtime.before_delivery(event) is False
    runtime.judge.assert_not_awaited()


async def test_changed_ordinary_context_can_cancel_stale_reply(runtime):
    event=pending(runtime)
    runtime.observe(Event('已经解决了'))
    runtime.judge.return_value=False
    assert await runtime.before_delivery(event) is False
    runtime.judge.assert_awaited_once()


async def test_already_started_segments_do_not_repeat_judgment(runtime):
    event=pending(runtime)
    assert await runtime.before_delivery(event) is True
    runtime.observe(Event('旁边聊别的'))
    assert await runtime.before_delivery(event) is True
    runtime.judge.assert_not_awaited()


async def test_revision_changing_during_recheck_cancels_delivery(runtime):
    event=pending(runtime);runtime.observe(Event('新话题'))
    async def judge(*args):
        runtime.observe(Event('又有新消息'));return True
    runtime.judge=judge
    assert await runtime.before_delivery(event) is False


@pytest.mark.parametrize('social,timing,expected',[(0,2,False),(2,0,False),(2,2,True)])
async def test_five_factor_social_and_timing_are_hard_negative(runtime,social,timing,expected):
    factors={'content':2,'interest':2,'social':social,'timing':timing,'continuity':1}
    response={'should_reply':True,'addressed_to_bot':True,'stop_conversation':False,'reason':'短判断','factors':factors}
    runtime.cap.context=NS(llm_generate=AsyncMock(return_value=NS(completion_text=json.dumps(response))))
    runtime.bot_id='bot'
    assert await IntentRuntime.judge(runtime,'scope',[]) is expected
    assert runtime.last_decisions['scope']['factors']==factors


async def test_owner_quiet_changed_during_recheck_still_blocks_transport():
    quiet=NS(value=False)
    quiet.suppress=lambda event:quiet.value
    class Message:
        sent=0
        async def send(self,*args,**kwargs):self.sent+=1
        def clear_result(self):pass
        def stop_event(self):pass
    async def check(event):
        quiet.value=True
        return True
    undo=install_send_guard(Message,quiet,check)
    try:
        event=Message();await event.send('synthetic')
        assert event.sent==0
    finally:undo()
