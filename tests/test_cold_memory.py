import hashlib
import json
import sqlite3
from datetime import datetime
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest
from astrbot_plugin_fish_capabilities.services.cold_memory import ColdMemory,redact
from astrbot_plugin_fish_capabilities.services.computer_link import link_status
from astrbot_plugin_fish_capabilities.services.sister_mail import SisterMail
from astrbot_plugin_fish_capabilities.services.policy import CapabilityError
from test_astrbot_binding import plugin,Event

S='qq_test:FriendMessage:10001'


def archive(tmp_path,when='2026-10-27T03:30:00+08:00'):
    now=[datetime.fromisoformat(when).timestamp()]
    return ColdMemory(tmp_path/'cold',clock=lambda:now[0]),now


def test_append_only_split_and_scope(tmp_path):
    c,t=archive(tmp_path)
    assert c.capture(S,'p','user','原话'+('a'*2500),'id')==3
    assert c.capture(S,'p','user','改写原话','id')==0
    assert c.capture('qq_test:GroupMessage:4','p','user','xx','id')==0
    assert c.capture(S,'','user','xx','id')==0
    assert c.recall(S,'other','原话')['excerpts']==[]
    c2=ColdMemory(c.root,clock=lambda:t[0])
    assert c2.recall(S,'p','原话')['excerpts'][0]['text'].startswith('原话a')
    with c.db() as db:row=db.execute('SELECT * FROM chunks WHERE part=0').fetchone()
    assert len(c.excerpt(row)['text'])==1200
    assert '改写' not in c.excerpt(row)['text']


def test_secret_redaction_before_disk(tmp_path):
    c,_=archive(tmp_path)
    secret='sk-'+'x'*40
    assert 'test-secret' not in redact('我的密码是 test-secret')
    c.capture(S,'p','user','原话\napi_key: '+secret+' more\nCookie: session=secret; other=x\nhttps://local.invalid/?token=hidden','m')
    for p in c.root.rglob('*.json'):
        body=p.read_text(encoding='utf-8')
        assert secret not in body and 'session=secret' not in body and 'token=hidden' not in body


def test_lookup_cooldown_literals_and_integrity(tmp_path):
    c,t=archive(tmp_path)
    c.capture(S,'p','user','我当时说可能去海洋公园，没定。','a')
    c.capture(S,'p','assistant','你还没决定。','b')
    assert c.recall(S,'p','海洋公园')['excerpts'][0]['role']=='user'
    assert c.recall(S,'p','没决定')['state']=='cooldown'
    t[0]+=301
    assert c.recall(S,'p','海洋公园')['state']=='same_cue_recently_read'
    t[0]+=3601
    assert c.recall(S,'p','%%')['excerpts']==[]
    with pytest.raises(CapabilityError):c.recall(S,'p','')
    with pytest.raises(CapabilityError):c.recall(S,'p','公园',3)
    with c.db() as db:row=db.execute('SELECT * FROM chunks WHERE role=?',('user',)).fetchone()
    target=c.root/row['file'];target.chmod(0o600);target.write_text('{}',encoding='utf-8')
    with pytest.raises(CapabilityError):c.excerpt(row)


async def test_dream_private_sources_once_and_restart(tmp_path):
    c,t=archive(tmp_path)
    c.capture(S,'p','user','我还没决定去哪里。','a',t[0]-86400)
    c.capture(S,'other','user','另一人格资料。','b',t[0]-86400)
    async def generate(excerpts):
        assert len(excerpts)==1
        return {'note':'回顾昨天：主人当时还没有决定。','sources':[{'id':excerpts[0]['id'],'quote':'还没决定去哪里'}]}
    g=AsyncMock(side_effect=generate)
    assert (await c.dream(S,'p',g,connected=False))['state']=='computer_not_connected'
    assert (await c.dream(S,'p',g,connected=True,recent_owner_at=t[0]-50))['state']=='recent_conversation'
    result=await c.dream(S,'p',g,connected=True)
    assert result['state']=='saved'
    c2=ColdMemory(c.root,clock=lambda:t[0])
    assert (await c2.dream(S,'p',g,connected=True))['state']=='already_attempted'
    assert g.await_count==1
    assert c.diaries(S,'other')['diaries']==[]
    diary=c.diaries(S,'p')['diaries'][0]
    assert diary['version']==1 and '没有决定' in diary['note']
    assert len(json.loads(diary['sources']))==1


@pytest.mark.parametrize('bad',[{'note':'凭空猜测','sources':[{'id':'fake','quote':'虚构的引用'}]}, {'note':'x','sources':[]},{}])
async def test_bad_dream_stops_without_retry(tmp_path,bad):
    c,t=archive(tmp_path);c.capture(S,'p','user','真实原话内容','a',t[0]-86400)
    g=AsyncMock(return_value=bad)
    assert (await c.dream(S,'p',g,connected=True))['state']=='failed_no_retry'
    assert (await c.dream(S,'p',g,connected=True))['state']=='already_attempted'
    assert not c.diaries(S,'p')['diaries']
    assert g.await_count==1


async def test_diary_correction_requires_owner_evidence_version_and_scope(tmp_path):
    c,t=archive(tmp_path);c.capture(S,'p','user','当时还没决定。','a',t[0]-86400)
    async def g(excerpts):return {'note':'当时没有决定。','sources':[{'id':excerpts[0]['id'],'quote':'还没决定。'}]}
    await c.dream(S,'p',g,connected=True)
    ident=c.diaries(S,'p')['diaries'][0]['id'];review=AsyncMock(return_value=True)
    with pytest.raises(CapabilityError):await c.correct_diary(S,'p',ident,1,'改了','明确更正的话','没有这句',review)
    with pytest.raises(CapabilityError):await c.correct_diary(S,'other',ident,1,'改了','明确更正的话','明确更正的话',review)
    result=await c.correct_diary(S,'p',ident,1,'后来主人明确说改计划了。','已经改计划了','我已经改计划了',review)
    assert result['version']==2 and not result['raw_archive_changed']
    with pytest.raises(CapabilityError):await c.correct_diary(S,'p',ident,1,'过期','已经改计划了','已经改计划了',review)
    with c.db() as db:assert db.execute('SELECT COUNT(*) FROM diary_edits').fetchone()[0]==1


def test_heartbeat_is_not_reader_presence(tmp_path):
    p=tmp_path/'computer-link.json'
    assert link_status(p)['state']=='unknown'
    p.write_text(json.dumps({'source':'local-computer-adb','at':1000}))
    s=link_status(p,lambda:1100)
    assert s['connected'] and not s['reader_active'] and not s['reader_notified']
    assert link_status(p,lambda:1600)['state']=='stale'
    p.write_text(json.dumps({'source':'local-computer-adb','at':2000}))
    assert link_status(p,lambda:1100)['state']=='unknown'


def test_mail_saved_read_and_replied_are_distinct(tmp_path):
    m=SisterMail(tmp_path/'sister-mail.sqlite3')
    ident=m.leave('fish','想写一封信')['id']
    assert m.status()['outgoing'][0]['state']=='waiting'
    assert m.read('codex')['letters']
    assert m.status()['outgoing'][0]['state']=='waiting'
    m.acknowledge('codex',ident)
    assert m.status()['outgoing'][0]['state']=='read'
    m.leave('codex','已看见',reply_to=ident)
    assert m.status()['outgoing'][0]['state']=='replied'


async def test_binding_tool_scope_and_quarantine(plugin):
    plugin.config.update(cold_archive_enabled=True,command_platform_ids=['qq_test'],bili_private_session=S)
    manager=NS(get_curr_conversation_id=AsyncMock(return_value='cid'),get_conversation=AsyncMock(return_value=NS(persona_id='p')))
    plugin.context=NS(conversation_manager=manager)
    event=Event();event.unified_msg_origin=S
    plugin.cold_memory.capture(S,'p','user','那天说了海洋公园。','old')
    result=json.loads(await plugin.cold_recall_tool(event,query='海洋公园'))
    assert result['excerpts']
    assert plugin.cold_memory.is_private_context(S,'cid')
    assert plugin.public_review.context().get('history') is None
    for e in (Event(private=False),Event(sender='other',admin=False)):
        assert json.loads(await plugin.cold_recall_tool(e,query='海洋公园'))['ok'] is False


async def test_current_private_context_not_copied_to_public(plugin):
    plugin.config.update(cold_archive_enabled=True,bili_public_review_enabled=True,command_platform_ids=['qq_test'],bili_private_session=S)
    plugin.context=NS(conversation_manager=NS(get_curr_conversation_id=AsyncMock(return_value='cid'),get_conversation=AsyncMock(return_value=NS(persona_id='p'))))
    event=Event();event.unified_msg_origin=S
    plugin.cold_memory.quarantine(S,'cid')
    req=NS(system_prompt='不应进入公开草稿',contexts=[],prompt='原文',extra_user_content_parts=[])
    await plugin.capture_bili_private_context(event,req)
    assert '原文' not in json.dumps(plugin.public_review.context(),ensure_ascii=False)


async def test_dream_unknown_outcome_not_retried_and_day_gate(tmp_path):
    c,t=archive(tmp_path,'2026-10-27T12:30:00+08:00')
    c.capture(S,'p','user','旧记录完整原话','a',t[0]-86400)
    g=AsyncMock(side_effect=TimeoutError())
    assert (await c.dream(S,'p',g,connected=True))['state']=='outside_night'
    t[0]=datetime.fromisoformat('2026-10-28T03:30:00+08:00').timestamp()
    assert (await c.dream(S,'p',g,connected=True))['state']=='failed_no_retry'
    assert (await c.dream(S,'p',g,connected=True))['state']=='already_attempted'
    assert g.await_count==1


def test_recall_local_daily_budget_survives_reload(tmp_path):
    c,t=archive(tmp_path,'2026-10-27T10:00:00+08:00')
    for i in range(12):
        assert c.recall(S,'p',f'线索{i}')['state']=='no_match'
        t[0]+=301
    other=ColdMemory(c.root,clock=lambda:t[0])
    assert other.recall(S,'p','别的线索')['state']=='daily_limit'
    assert not other.is_private_context(S,'cid')
    other.quarantine(S,'cid')
    assert c.is_private_context(S,'cid')


def test_archive_does_not_expand_media_or_tool_material():
    from astrbot_plugin_fish_capabilities.services.cold_memory import plain_text
    assert plain_text([{'type':'text','text':'原话'},{'type':'image_url','image_url':'private-file'}])=='原话'
    assert plain_text({'tool':'private'})==''


async def test_framework_default_persona_is_not_treated_as_unknown(plugin,monkeypatch):
    import sys
    from astrbot_plugin_fish_capabilities.services.cold_memory import resolve_persona
    api=sys.modules['astrbot.api']
    monkeypatch.setattr(api,'sp',NS(get_async=AsyncMock(return_value={})),raising=False)
    context=NS(persona_manager=NS(get_default_persona_v3=AsyncMock(return_value={'name':'default-p'})))
    assert await resolve_persona(context,S,NS(persona_id=None))=='default-p'
    assert await resolve_persona(context,S,NS(persona_id='conversation-p'))=='conversation-p'
    api.sp.get_async=AsyncMock(return_value={'persona_id':'override-p'})
    assert await resolve_persona(context,S,NS(persona_id='conversation-p'))=='override-p'
    api.sp.get_async=AsyncMock(return_value={'persona_id':'[%None]'})
    assert await resolve_persona(context,S,NS(persona_id='conversation-p')) is None


async def test_public_writes_reject_archive_turn_before_network(plugin):
    plugin.config.update(cold_archive_enabled=True,bili_comment_enabled=True,bili_reply_enabled=True,bili_activity_enabled=True,bili_public_review_enabled=True)
    event=Event();event.set_extra('fish_cold_private_context',True)
    with pytest.raises(CapabilityError,match='冷档'):plugin.enabled('bili_comment',event,owner=True)
    with pytest.raises(CapabilityError,match='冷档'):plugin.enabled('bili_reply',event,owner=True)
    plugin.bili_activity.post=AsyncMock()
    result=json.loads(await plugin.bili_activity_tool(event,action='post',text='原文不该公开'))
    assert result['ok'] is False
    plugin.bili_activity.post.assert_not_awaited()
    result=json.loads(await plugin.bili_review_tool(event,action='approve',draft_id='any'))
    assert result['ok'] is False
