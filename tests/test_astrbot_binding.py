"""Contract tests using explicit AstrBot stubs, not an actual running bot."""
import importlib
import json
import sys
import types

import pytest

from test_services import VoiceFake, make_library


class Event:
    def __init__(self, *, private=True, sender='10001', admin=True):
        self.private=private; self.sender=sender; self.admin=admin
        self.extras={}; self.result=types.SimpleNamespace(chain=[])
    def get_sender_id(self): return self.sender
    def get_platform_id(self): return 'qq_test'
    def is_private_chat(self): return self.private
    def is_admin(self): return self.admin
    def get_group_id(self): return '' if self.private else '77777'
    def get_extra(self,key): return self.extras.get(key)
    def set_extra(self,key,value): self.extras[key]=value
    def get_result(self): return self.result


@pytest.fixture
def plugin(tmp_path,monkeypatch):
    root=tmp_path/'data/plugin_data/astrbot_plugin_fish_capabilities'
    def module(name,**entries):
        value=types.ModuleType(name);value.__dict__.update(entries)
        monkeypatch.setitem(sys.modules,name,value)
        return value
    def decorator(*args,**kwargs): return lambda f:f
    class Star:
        def __init__(self,context): pass
    class Component:
        @classmethod
        def fromBase64(cls,data,**kwargs): return {'base64':data,**kwargs}
    module('astrbot')
    module('astrbot.api',AstrBotConfig=dict,logger=types.SimpleNamespace(warning=lambda *a:None))
    module('astrbot.api.event',AstrMessageEvent=Event,filter=types.SimpleNamespace(event_message_type=decorator,EventMessageType=types.SimpleNamespace(ALL="ALL"),llm_tool=decorator,on_decorating_result=decorator,on_llm_request=decorator,after_message_sent=decorator,on_llm_response=decorator))
    module('astrbot.api.star',Star=Star,Context=object,StarTools=types.SimpleNamespace(get_data_dir=lambda name:root))
    module('astrbot.api.message_components',Image=Component,Record=Component)
    name='astrbot_plugin_fish_capabilities.main'
    sys.modules.pop(name,None)
    binding=importlib.import_module(name)
    config={'enabled':True,'owners':['10001'],'meme_enabled':True,'tts_enabled':True,
            'media_cooldown_seconds':0,'media_hourly_limit':6,'allowed_group_sessions':['qq_test:GroupMessage:77777']}
    instance=binding.FishCapabilities(None,config)
    instance.speech.backend=VoiceFake()
    yield instance
    sys.modules.pop(name,None)


async def test_media_attaches_once_after_multiple_tool_calls(plugin):
    make_library(plugin.root/'memes')
    event=Event()
    assert json.loads(await plugin.meme_tool(event,'happy'))['queued']
    assert json.loads(await plugin.speak_tool(event,'你好'))['ok'] is False
    assert plugin.speech.backend.calls==0  # Reject before paid synthesis.
    await plugin.append_media(event)
    await plugin.append_media(event)
    assert len(event.result.chain)==1


async def test_voice_failed_delivery_not_blindly_resubmitted(plugin):
    event=Event()
    assert json.loads(await plugin.speak_tool(event,'你好'))['queued']
    await plugin.append_media(event)
    # Treat decoration as handoff; even if QQ transport later times out, never
    # synthesize/send another copy in this input turn.
    assert json.loads(await plugin.speak_tool(event,'再来一次'))['ok'] is False
    assert plugin.speech.backend.calls==1


async def test_disable_before_decoration_cancels_output(plugin):
    event=Event()
    await plugin.speak_tool(event,'你好')
    plugin.config['enabled']=False
    await plugin.append_media(event)
    assert event.result.chain==[]


async def test_groups_cannot_use_owner_history_or_bili(plugin):
    plugin.config.update(history_enabled=True,bili_enabled=True)
    event=Event(private=False)
    assert json.loads(await plugin.group_history(event,'77777'))['ok'] is False
    assert json.loads(await plugin.bili_browse(event))['ok'] is False


async def test_quota_allowed_in_authorized_group_only(plugin):
    from unittest.mock import AsyncMock
    plugin.config['quota_enabled']=True
    plugin.quota.get=AsyncMock(return_value={'provider':'DeepSeek'})
    assert json.loads(await plugin.quota_tool(Event(private=False,sender='someone',admin=False)))['provider']=='DeepSeek'
    plugin.quota.get.assert_awaited_once()
    plugin.config['allowed_group_sessions']=[]
    assert json.loads(await plugin.quota_tool(Event(private=False)))['ok'] is False
    assert json.loads(await plugin.quota_tool(Event(sender='someone',admin=False)))['ok'] is False
    assert plugin.quota.get.await_count==1


async def test_enabled_tools_are_reactivated_after_previous_disable(plugin):
    from unittest.mock import AsyncMock,Mock
    plugin.config.update(tts_enabled=False,meme_enabled=True)
    plugin.context=types.SimpleNamespace(activate_llm_tool_async=AsyncMock(),deactivate_llm_tool=Mock())
    await plugin.initialize()
    activated={call.args[0] for call in plugin.context.activate_llm_tool_async.await_args_list}
    deactivated={call.args[0] for call in plugin.context.deactivate_llm_tool.call_args_list}
    assert {'fish_meme','fish_meme_catalog'}<=activated
    assert 'fish_speak' in deactivated and 'fish_speak' not in activated


async def test_meme_catalog_gives_balanced_overview_and_keyword_search(plugin):
    from astrbot_plugin_fish_capabilities.services.memes import Meme
    entries=[Meme(str(i),'tease',plugin.root/'unused',(),str(i),description='轻松吐槽',image_text='摸鱼') for i in range(70)]
    entries.append(Meme('night','goodnight',plugin.root/'unused',('晚安',),'night-hash',description='困了睡觉',image_text='晚安'))
    plugin.memes.catalog=lambda:entries
    overview=json.loads(await plugin.meme_catalog(Event()))
    assert len(overview['memes'])==3 and any(r['id']=='night' for r in overview['memes'])
    selected=json.loads(await plugin.meme_catalog(Event(),query='晚安'))
    assert [r['id'] for r in selected['memes']]==['night']
    assert len(json.loads(await plugin.meme_catalog(Event(),category='tease'))['memes'])==16


async def test_default_off_cannot_make_network_call(plugin):
    plugin.config.clear()
    assert json.loads(await plugin.weather_tool(Event(),'杭州'))['reason']=='这个能力尚未启用。'


async def test_failed_paid_synthesis_cannot_retry_this_turn(plugin):
    from test_services import VoiceFake
    plugin.speech.backend=VoiceFake(fail=True)
    event=Event()
    assert json.loads(await plugin.speak_tool(event,'你好'))['ok'] is False
    assert json.loads(await plugin.speak_tool(event,'重新合成'))['ok'] is False
    assert plugin.speech.backend.calls==1
    await plugin.append_media(event)
    assert event.result.chain==[]


async def test_duplicate_qq_event_does_not_resynthesize(plugin):
    first=Event();first.message_obj=types.SimpleNamespace(message_id='qq-test-123')
    second=Event();second.message_obj=types.SimpleNamespace(message_id='qq-test-123')
    assert json.loads(await plugin.speak_tool(first,'你好'))['queued']
    await plugin.append_media(first)
    assert json.loads(await plugin.speak_tool(second,'你好'))['ok'] is False
    assert plugin.speech.backend.calls==1


async def test_group_video_owner_direct_others_need_owner(plugin,monkeypatch):
    from unittest.mock import AsyncMock
    from test_services import BV
    from astrbot_plugin_fish_capabilities.services.bili_consent import Consent
    from astrbot_plugin_fish_capabilities.services.bilibili import BiliReader
    from test_services import BiliFake
    comp=sys.modules['astrbot.api.message_components']
    class Plain:
        def __init__(self,text):self.text=text
    class Reply:
        def __init__(self,sender_id,message_str):self.sender_id=sender_id;self.message_str=message_str;self.chain=[]
    monkeypatch.setattr(comp,'Plain',Plain,raising=False)
    monkeypatch.setattr(comp,'Reply',Reply,raising=False)
    plugin.config['bili_group_enabled']=True
    plugin.bili_consent=Consent(BiliReader(plugin.root/'test-consent.db',BiliFake()))
    plugin.bili.read=AsyncMock(return_value={'video_id':BV})
    def ev(sender,text,reply=None):
        e=Event(private=False,sender=sender,admin=sender=='10001')
        e.unified_msg_origin='qq_test:GroupMessage:77777'
        e.message_obj=types.SimpleNamespace(self_id='bot')
        e.get_messages=lambda:[Plain(text)]+([reply] if reply else [])
        return e
    assert json.loads(await plugin.bili_group_watch(ev('10001','看看这个视频'),BV))['video_id']==BV
    assert plugin.bili.read.await_count==1
    other=ev('other','看看这个视频')
    assert json.loads(await plugin.bili_group_watch(other,BV))['needs_owner_confirmation']
    assert other.get_extra('fish_bili_consent_request')['owner']=='10001'
    assert plugin.bili.read.await_count==1
    assert not json.loads(await plugin.bili_group_watch(ev('other','同意')))['ok']
    assert not json.loads(await plugin.bili_group_watch(ev('10001','不同意'),BV))['ok']
    assert not json.loads(await plugin.bili_group_watch(ev('10001','看吧',Reply('other',BV))))['ok']
    assert json.loads(await plugin.bili_group_watch(ev('10001','看吧',Reply('bot',BV))))['video_id']==BV
    assert plugin.bili.read.await_count==2
    assert not json.loads(await plugin.bili_group_watch(ev('10001','同意')))['ok']


async def test_private_activity_never_injected_in_group_or_other_private(plugin):
    plugin.config.update(command_platform_ids=['qq_test'],bili_enabled=True)
    plugin.private_ping=types.SimpleNamespace(activities=lambda:[{'kind':'pending','note':'私人待办标记'}])
    private=Event();req=types.SimpleNamespace(system_prompt='')
    await plugin.clarify_group_targets(private,req)
    assert '私人待办标记' in req.system_prompt and 'fish_bili_browse' in req.system_prompt
    other=Event(sender='other');req=types.SimpleNamespace(system_prompt='')
    await plugin.clarify_group_targets(other,req);assert '私人待办标记' not in req.system_prompt
    group=Event(private=False);group.get_self_id=lambda:'bot';group.get_messages=lambda:[]
    req=types.SimpleNamespace(system_prompt='');await plugin.clarify_group_targets(group,req)
    assert '私人待办标记' not in req.system_prompt


async def test_authorized_group_has_explicit_bili_tool_guidance(plugin):
    plugin.config['bili_group_enabled']=True
    event=Event(private=False);event.get_self_id=lambda:'bot';event.get_messages=lambda:[]
    req=types.SimpleNamespace(system_prompt='')
    await plugin.clarify_group_targets(event,req)
    assert '[当前群B站读取权限已启用]' in req.system_prompt and '无需再次确认' in req.system_prompt
    event.sender='someone';event.admin=False;req=types.SimpleNamespace(system_prompt='')
    await plugin.clarify_group_targets(event,req)
    assert '登记申请并@主人' in req.system_prompt
    plugin.config['allowed_group_sessions']=[];req=types.SimpleNamespace(system_prompt='')
    await plugin.clarify_group_targets(event,req)
    assert '[当前群B站读取权限已启用]' not in req.system_prompt


async def test_meme_autonomy_prompt_matches_current_limits(plugin):
    plugin.config.update(media_cooldown_seconds=0,meme_min_reply_gap=0,media_hourly_limit=6)
    req=types.SimpleNamespace(system_prompt='')
    await plugin.clarify_group_targets(Event(),req)
    assert '已取消固定轮次间隔和时间冷却' in req.system_prompt
    assert '每小时最多6张' in req.system_prompt


async def test_background_limit_is_real_extra_body_and_does_not_mutate_chat(plugin):
    calls=[]
    class Provider:
        provider_config={'custom_extra_body':{'temperature':0.7}}
        async def text_chat(self,**kwargs):
            calls.append((dict(self.provider_config['custom_extra_body']),kwargs))
            return types.SimpleNamespace(completion_text='ok',usage=None)
    original=Provider();plugin.context=types.SimpleNamespace(get_provider_by_id=lambda name:original)
    result=await plugin.bounded_generate('deepseek/test',prompt='test',system_prompt='test',max_tokens=120,timeout=1)
    assert result.completion_text=='ok' and calls[0][0]['max_tokens']==120
    assert calls[0][0]['thinking']=={'type':'disabled'}
    assert 'thinking' not in original.provider_config['custom_extra_body']
    assert 'max_tokens' not in original.provider_config['custom_extra_body']
    assert calls[0][1]['request_max_retries']==1


async def test_context_budget_supports_gcp_without_request_conversation(plugin):
    from unittest.mock import AsyncMock
    plugin.config['context_budget_enabled']=True
    plugin.context=types.SimpleNamespace(conversation_manager=types.SimpleNamespace(get_curr_conversation_id=AsyncMock(return_value='group-cid'),get_conversation=AsyncMock(return_value=types.SimpleNamespace(persona_id='fish'))))
    plugin.context_budget.prepare=AsyncMock(return_value=([],{'outcome':'test'}))
    event=Event(private=False);event.unified_msg_origin='qq_test:GroupMessage:77777'
    req=types.SimpleNamespace(conversation=None,contexts=[],system_prompt='',prompt='test')
    await plugin.budget_context(event,req)
    assert plugin.context_budget.prepare.await_args.args[0]=='qq_test:GroupMessage:77777|group-cid|fish'
    assert event.get_extra('fish_context_metrics')['outcome']=='test'


async def test_long_ordinary_reply_split_and_non_owner_private_untouched(plugin,monkeypatch):
    comp=sys.modules['astrbot.api.message_components']
    class Plain:
        def __init__(self,text):self.text=text
    monkeypatch.setattr(comp,'Plain',Plain,raising=False)
    plugin.config.update(ordinary_segment_enabled=True,command_platform_ids=['qq_test'])
    event=Event();text='这是一段完整保留的长回复。'*30
    event.result.chain=[Plain(text)];event.result.is_model_result=lambda:True
    await plugin.split_ordinary_reply(event)
    assert len(event.result.chain)>1 and ''.join(c.text for c in event.result.chain)==text
    other=Event(sender='other');other.result.chain=[Plain(text)];other.result.is_model_result=lambda:True
    await plugin.split_ordinary_reply(other);assert len(other.result.chain)==1
