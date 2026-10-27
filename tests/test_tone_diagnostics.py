import json
import sqlite3
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from astrbot_plugin_fish_capabilities.services.tone_diagnostics import analyze,ToneDiagnostics
from astrbot_plugin_fish_capabilities.services.policy import CapabilityError
from test_astrbot_binding import plugin,Event


def test_context_supports_real_steps_and_correction_but_does_not_delete_normal_phrases():
    text='你说得对。先打开设置，再找到插件。'
    result=analyze(text,'纠正一下，给我列出安装步骤')
    assert result['scene']=='steps'
    assert all(h['assessment']=='context_supported' for h in result['hits'])
    assert result['text_changed'] is False and result['model_calls']==0
    assert analyze(text,'今天下课啦')['status']=='hints_found'


def test_unrequested_priority_and_dense_frames_are_hints_not_an_ai_verdict():
    text='你说得对。真要只挑一件，我想看海。不是要讲道理，而是想聊天。'
    result=analyze(text,'刚回到家')
    assert result['clusters'] and {h['code'] for h in result['hits']} >= {'receipt','priority','contrast'}
    assert '不是人味评分' in result['instruction']
    assert 'score' not in result


def test_quotes_code_links_and_actual_data_are_protected():
    result=analyze('“这一点我认”\n```\n真要只挑一件\n```\nhttps://example.com/首先\n> 你说得对。\n10:30，价格128元，KD 1.25。','给我今日商店')
    assert result['scene']=='data' and result['protected_spans']>=5
    assert result['hits']==[]


def test_reports_are_scoped_deduplicated_and_never_store_originals(tmp_path):
    clock=[1000];store=ToneDiagnostics(tmp_path/'tone.db',lambda:clock[0])
    for ending in ('甲','乙','丙'):
        store.record('private','这一点我认。PRIVATE_CANARY_'+ending,'CONTEXT_SECRET')
        clock[0]+=10
    records=store.recent('private')['records']
    assert records[0]['recent_opening_repeats']==[{'code':'receipt','previous_turns':2}]
    assert not store.recent('group')['records']
    store.record('private','这一点我认。PRIVATE_CANARY_丙','CONTEXT_SECRET')
    assert len(store.recent('private')['records'])==3
    with sqlite3.connect(store.path) as db:dump='\n'.join(db.iterdump())
    assert 'PRIVATE_CANARY' not in dump and 'CONTEXT_SECRET' not in dump
    assert '这一点我认' not in dump
    clock[0]+=15*86400;store.record('private','今天挺开心的')
    assert len(store.recent('private')['records'])==1


@pytest.mark.parametrize('value',[None,[],{},''])
def test_bad_manual_inputs_fail_without_text_processing(value):
    with pytest.raises(CapabilityError):analyze(value)


async def test_hook_preserves_exact_response_and_does_not_call_model(plugin):
    plugin.config.update(tone_diagnostics_enabled=True,command_platform_ids=['qq_test'])
    response=SimpleNamespace(completion_text='这一点我认。真要只挑一件，我想看鲸鱼。')
    before=response.completion_text
    plugin.context=SimpleNamespace(llm_generate=AsyncMock())
    event=Event();event.get_message_str=lambda:'今天下课了'
    await plugin.diagnose_reply_style(event,response)
    assert response.completion_text==before
    plugin.context.llm_generate.assert_not_awaited()
    assert plugin.companion.tone.recent('qq_test:FriendMessage:10001')['records']
    result=json.loads(await plugin.tone_diagnose_tool(Event(sender='other'),'测试'))
    assert result['ok'] is False


async def test_admin_manual_diagnosis_does_not_store_input(plugin):
    from astrbot_plugin_fish_capabilities.services.companion_page import CompanionPage
    plugin.config.update(tone_diagnostics_enabled=True,bili_private_session='qq_test:FriendMessage:10001')
    page=CompanionPage(plugin,plugin.companion)
    result=await page.perform({'operation':'tone_diagnose','text':'真要只挑一件，我想看海。','context':'我到家了'})
    assert result['status']=='hints_found'
    assert not plugin.companion.tone.recent('qq_test:FriendMessage:10001')['records']
