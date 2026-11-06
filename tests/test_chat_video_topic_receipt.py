import json
from types import SimpleNamespace as NS
import pytest
from test_astrbot_binding import plugin,Event
from test_bili_comments import prepared
from test_video_initiative import make_ping


async def prepare_case(plugin,tmp_path,monkeypatch):
    from astrbot.api import message_components as Comp
    class Plain:
        def __init__(self,text):self.text=text
    monkeypatch.setattr(Comp,'Plain',Plain,raising=False)
    reader,packet,_=await prepared(tmp_path)
    ping,clock,*_=await make_ping(tmp_path)
    ident=ping.offer_video(packet)
    plugin.bili=reader;plugin.private_ping=ping;plugin.config.update(bili_enabled=True,command_platform_ids=['qq_test'])
    event=Event();event.set_extra('fish_video_topic_candidates',[ident])
    return ping,clock,ident,event,Plain


def state(ping,ident):
    with ping.db() as db:return db.execute('SELECT state FROM topic_states WHERE id=?',(ident,)).fetchone()[0]


async def test_declared_topic_requires_all_accepted_model_segments(plugin,tmp_path,monkeypatch):
    ping,clock,ident,event,Plain=await prepare_case(plugin,tmp_path,monkeypatch)
    result=json.loads(await plugin.bili_memory(event,use_topic_id=ident))
    assert result['topic_use']=='prepared_not_sent' and state(ping,ident)=='pending'
    event.result=NS(chain=[],is_llm_result=lambda:False)
    plugin.capture_private_delivery(event,NS(chain=[Plain('我先看看')]))
    assert state(ping,ident)=='pending'  # Tool acknowledgement is not the final reply.
    one,two=Plain('我倒觉得这个画面挺有趣'),Plain('它后面居然又回来了')
    event.result=NS(chain=[one,two],is_llm_result=lambda:True)
    plugin.capture_private_delivery(event,NS(chain=[one]))
    assert state(ping,ident)=='pending'  # A partial response is insufficient.
    plugin.capture_private_delivery(event,NS(chain=[two]))
    assert state(ping,ident)=='discussed',event.extras
    assert not event.get_extra('fish_video_topic_use')
    assert ping.video_candidates()[0]['state']=='discussed'  # Still searchable history.
    assert not ping.video_candidates(pending_only=True)
    clock[0]+=3600
    assert await ping.tick()=='no_context'  # Not an unsolicited candidate again.


async def test_query_only_and_runner_error_do_not_consume_topic(plugin,tmp_path,monkeypatch):
    ping,clock,ident,event,Plain=await prepare_case(plugin,tmp_path,monkeypatch)
    await plugin.bili_memory(event)
    assert not event.get_extra('fish_video_topic_use')
    await plugin.bili_memory(event,use_topic_id=ident)
    failure=Plain('生成出了点问题')
    event.result=NS(chain=[failure],is_llm_result=lambda:False)
    plugin.capture_private_delivery(event,NS(chain=[failure]))
    assert state(ping,ident)=='pending'


@pytest.mark.parametrize('case',['unknown','group','other','reserved','expired_plan'])
async def test_topic_claim_is_scoped_current_and_cannot_overwrite_other_delivery(plugin,tmp_path,monkeypatch,case):
    ping,clock,ident,event,Plain=await prepare_case(plugin,tmp_path,monkeypatch)
    if case=='unknown':event.set_extra('fish_video_topic_candidates',[])
    if case=='group':event.private=False
    if case=='other':event.sender='other'
    if case=='reserved':
        with ping.db() as db:db.execute("UPDATE topic_states SET state='reserved' WHERE id=?",(ident,))
    result=json.loads(await plugin.bili_memory(event,use_topic_id=ident))
    if case!='expired_plan':
        assert result['ok'] is False and not event.get_extra('fish_video_topic_use')
    else:
        assert result['topic_use']=='prepared_not_sent';clock[0]+=901
        text=Plain('这个画面让我想到一件事')
        event.result=NS(chain=[text],is_llm_result=lambda:True)
        plugin.capture_private_delivery(event,NS(chain=[text]))
        assert state(ping,ident)=='pending'


async def test_deferred_topic_is_not_offered_to_autonomy_before_due(plugin,tmp_path,monkeypatch):
    ping,clock,ident,event,Plain=await prepare_case(plugin,tmp_path,monkeypatch)
    with ping.db() as db:db.execute("UPDATE topic_states SET state='deferred',not_before=? WHERE id=?",(clock[0]+3600,ident))
    assert not ping.video_candidates(pending_only=True)
    assert ping.video_candidates()[0]['id']==ident  # Owner's explicit recall remains available.
    clock[0]+=3600
    assert ping.video_candidates(pending_only=True)[0]['id']==ident

