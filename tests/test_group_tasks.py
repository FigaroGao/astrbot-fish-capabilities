from unittest.mock import AsyncMock
import pytest
from astrbot_plugin_fish_capabilities.services.group_tasks import task_reason,skip_group_task
from test_intent_runtime import runtime,Event,Gcp,consume
from test_astrbot_binding import plugin

@pytest.mark.parametrize('text',['1+1等于多少','123×456=?','2+3','帮我解方程','帮我证明勾股定理','帮我写一个排序算法','能不能帮我调试这个程序'])
def test_explicit_tasks_are_filtered(text):assert task_reason(text)

@pytest.mark.parametrize('text',['今天3点上课','EDG 13:7赢了','2026-10-24','刚才1打3真帅','我吃了2/3的蛋糕','https://example.com/2+3','AI芯片为什么有意思','帮我分析这把战绩','不要算题了，聊天吧','别算算术了'])
def test_normal_conversation_not_filtered(text):assert task_reason(text) is None

async def test_direct_math_never_calls_judge_or_reply_and_next_chat_survives(runtime):
    runtime.cap.config['group_skip_complex_tasks']=True
    g=Gcp()
    e=Event('1+1等于多少',True)
    assert await consume(runtime,g,e)==[] and e.call_llm
    runtime.judge.assert_not_awaited()
    assert g.calls==0
    assert await consume(runtime,g,Event('聊聊鲸鱼吧',True))
    assert g.calls==1


def test_private_and_disabled_are_unchanged():
    e=Event('1+1=?',True)
    c={'enabled':True,'group_skip_complex_tasks':True,'allowed_group_sessions':[e.unified_msg_origin]}
    assert skip_group_task(c,e)
    e.is_private_chat=lambda:True
    assert skip_group_task(c,e) is None
    e.is_private_chat=lambda:False;c['group_skip_complex_tasks']=False
    assert skip_group_task(c,e) is None


async def test_message_and_model_hooks_stop_without_sending(plugin):
    from test_astrbot_binding import Event as BoundEvent
    e=BoundEvent(private=False)
    e.unified_msg_origin='qq_test:GroupMessage:77777'
    e.get_message_str=lambda:'请帮我解方程'
    e.stop_event=AsyncMock()  # replaced below with synchronous framework method
    stopped=[];e.stop_event=lambda:stopped.append(True)
    plugin.config['group_skip_complex_tasks']=True
    await plugin.skip_group_problem_request(e)
    await plugin.skip_group_problem_llm(e,None)
    assert len(stopped)==2 and e.get_result().chain==[]
