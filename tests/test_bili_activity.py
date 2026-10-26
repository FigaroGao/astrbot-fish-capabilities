import json,types
from datetime import datetime,timedelta,timezone
from unittest.mock import AsyncMock
import pytest
from astrbot_plugin_fish_capabilities.services.bilibili import BiliReader
from astrbot_plugin_fish_capabilities.services.bili_activity import BiliActivity,ActivityBackend
from astrbot_plugin_fish_capabilities.services.policy import CapabilityError
from test_services import BiliFake
from test_astrbot_binding import plugin,Event


class Backend:
    def __init__(self):self.who='42';self.online=False;self.fail=False;self.sent=[];self.feed_calls=[]
    async def identity(self):return self.who
    async def live(self,account):
        if self.fail:raise TimeoutError()
        return {'uid':account,'name':'指定UP','online':self.online,'title':'测试直播','url':'https://live.bilibili.com/123'}
    async def post(self,text):
        self.sent.append(text)
        if self.fail:raise TimeoutError('secret transport data')
        return '12345'
    async def feed(self,host):
        self.feed_calls.append(host)
        return {'items':[{'id_str':'88','type':'DYNAMIC_TYPE_WORD','modules':{'module_author':{'name':'UP','pub_ts':12},'module_dynamic':{'desc':{'text':'公开动态'}}}}],'has_more':True}
    async def messages(self,kind):return {'items':[{'id':99,'user':{'nickname':'测试人'},'item':{'source_content':'公开留言','token':'must not return'}}]}


def make(tmp_path):
    reader=BiliReader(tmp_path/'b.db',BiliFake());backend=Backend()
    now=[datetime(2026,10,25,10,tzinfo=timezone(timedelta(hours=8))).timestamp()]
    context={'at':now[0],'history':[{'text':'private context only in drafting'}]}
    review=types.SimpleNamespace(gate=AsyncMock(),pending=AsyncMock(),notices=AsyncMock(),context=lambda:context)
    cfg=dict(enabled=True,bili_enabled=True,bili_account_id='42',bili_activity_enabled=True,bili_live_watch_enabled=True,bili_dynamic_post_enabled=True,bili_dynamic_auto_enabled=True)
    generate=AsyncMock(return_value={'post':True,'text':'今天也想慢慢晃一会儿。'});notify=AsyncMock()
    activity=BiliActivity(reader,cfg,review,generate,notify,backend,clock=lambda:now[0])
    return activity,backend,review,generate,notify,now,context


async def test_live_selected_only_transition_and_restart_dedup(tmp_path):
    a,b,r,g,n,t,c=make(tmp_path)
    await a.watch('7');assert a.watches()['watching']==[{'uid':'7','name':'指定UP'}]
    await a.poll();n.assert_not_called()
    b.online=True;t[0]+=601;await a.poll();n.assert_awaited_once()
    assert '开播啦' in n.call_args.args[0]
    other=BiliActivity(a.reader,a.config,r,g,n,b,clock=lambda:t[0]);t[0]+=601
    await other.poll();n.assert_awaited_once()
    await a.watch('7',remove=True);assert not a.watches()['watching']


async def test_first_online_is_baseline_not_catchup_notice(tmp_path):
    a,b,r,g,n,t,c=make(tmp_path);b.online=True
    await a.watch('7');await a.poll();n.assert_not_called()


async def test_failed_poll_does_not_reset_online_and_create_duplicate(tmp_path):
    a,b,r,g,n,t,c=make(tmp_path);b.online=True
    await a.watch('7');b.fail=True;await a.poll()
    b.fail=False;t[0]+=601;await a.poll();n.assert_not_called()


async def test_live_notification_error_is_not_replayed(tmp_path):
    a,b,r,g,n,t,c=make(tmp_path);await a.watch('7');b.online=True
    n.side_effect=TimeoutError();await a.poll();assert n.await_count==1
    t[0]+=601;await a.poll();assert n.await_count==1


async def test_feed_and_notification_reads_do_not_access_private_messages(tmp_path):
    a,b,r,g,n,t,c=make(tmp_path)
    value=await a.feed();assert value['items'][0]['text']=='公开动态'
    assert 'token' not in json.dumps(await a.messages('at'))
    with pytest.raises(CapabilityError):await a.messages('private')
    assert not b.sent


async def test_account_mismatch_and_disabled_feature_never_post(tmp_path):
    a,b,r,g,n,t,c=make(tmp_path);b.who='99'
    with pytest.raises(CapabilityError):await a.post('普通碎碎念')
    assert not b.sent;r.gate.assert_not_called()
    b.who='42';a.config['bili_dynamic_post_enabled']=False
    with pytest.raises(CapabilityError):await a.post('普通碎碎念')


async def test_all_dynamic_writes_require_review_and_reserve_daily_limit(tmp_path):
    a,b,r,g,n,t,c=make(tmp_path)
    result=await a.post('今天想发会呆。')
    assert result['submitted'] and b.sent==['今天想发会呆。']
    assert r.gate.call_args.args[:3]==('dynamic',{'source':'manual'},'今天想发会呆。')
    with pytest.raises(CapabilityError):await a.post('同一天另一条。')
    assert len(b.sent)==1
    t[0]+=86400;await a.post('第二天的新碎碎念。');assert len(b.sent)==2


async def test_uncertain_dynamic_post_is_persistent_pause_not_retry(tmp_path):
    a,b,r,g,n,t,c=make(tmp_path);b.fail=True
    with pytest.raises(CapabilityError):await a.post('想说两句。')
    b.fail=False;t[0]+=86400
    with pytest.raises(CapabilityError):await a.post('不能换个正文重发。')
    assert len(b.sent)==1
    r.pending.assert_awaited_once();r.notices.assert_awaited_once()


async def test_review_denied_never_consumes_post_budget(tmp_path):
    a,b,r,g,n,t,c=make(tmp_path);r.gate.side_effect=CapabilityError('待主人确认')
    with pytest.raises(CapabilityError):await a.post('草稿。')
    assert not b.sent
    with a.reader.connect() as db:assert db.execute('SELECT COUNT(*) FROM bili_dynamic_posts').fetchone()[0]==0


async def test_thinking_new_context_hourly_and_can_choose_silence(tmp_path):
    a,b,r,g,n,t,c=make(tmp_path);g.return_value={'post':False}
    assert (await a.think())['state']=='chose_silence';assert g.await_count==1
    assert (await a.think())['state']=='no_new_context'
    c['at']+=60;t[0]+=60;assert (await a.think())['state']=='already_thought'
    t[0]+=3600;await a.think();assert g.await_count==2 and not b.sent


async def test_autonomous_post_is_reviewed_and_not_repeated_same_day(tmp_path):
    a,b,r,g,n,t,c=make(tmp_path)
    await a.think();assert len(b.sent)==1 and r.gate.call_args.args[0]=='dynamic'
    c['at']+=3600;t[0]+=3600;assert (await a.think())['state']=='daily_limit';assert g.await_count==1


async def test_quiet_hours_do_not_call_model(tmp_path):
    a,b,r,g,n,t,c=make(tmp_path);t[0]+=14*3600
    assert (await a.think())['state']=='quiet_hours';g.assert_not_called()


async def test_activity_tool_owner_private_only(plugin):
    plugin.config['bili_activity_enabled']=True
    plugin.bili_activity=types.SimpleNamespace(feed=AsyncMock(return_value={'items':[]}))
    for e in (Event(private=False),Event(sender='other'),Event(admin=False)):
        assert not json.loads(await plugin.bili_activity_tool(e))['ok']
    plugin.bili_activity.feed.assert_not_called()
    assert json.loads(await plugin.bili_activity_tool(Event()))=={'items':[]}


async def test_sdk_dynamic_builder_is_plain_text_no_at_or_private_message(monkeypatch):
    import sys
    builder=types.SimpleNamespace(add_plain_text=lambda text:('plain',text))
    send=AsyncMock(return_value={'dyn_id_str':'12345'})
    dynamic=types.SimpleNamespace(BuildDynamic=types.SimpleNamespace(empty=lambda:builder),send_dynamic=send)
    monkeypatch.setitem(sys.modules,'bilibili_api',types.SimpleNamespace(dynamic=dynamic))
    b=ActivityBackend(None);b.credential='synthetic'
    assert await b.post('普通文字')=='12345'
    send.assert_awaited_once_with(('plain','普通文字'),credential='synthetic')
