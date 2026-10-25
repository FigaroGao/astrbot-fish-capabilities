import asyncio
import json
import types
from unittest.mock import AsyncMock

import pytest
from astrbot_plugin_fish_capabilities.services.bili_actions import BiliActions, ActionBackend
from astrbot_plugin_fish_capabilities.services.bilibili import BiliReader
from astrbot_plugin_fish_capabilities.services.policy import CapabilityError
from test_services import BiliFake, BV
from test_astrbot_binding import plugin, Event


class Backend:
    def __init__(self):
        self.present = set()
        self.calls = []
        self.identity = AsyncMock(return_value='42')
        self.fail = False

    async def check(self, kind, video, account, folder):
        return (kind, video, folder) in self.present

    async def send(self, kind, video, folder):
        self.calls.append((kind, video, folder))
        if self.fail: raise TimeoutError('do not expose sensitive server response')
        self.present.add((kind, video, folder))


async def make(tmp_path):
    reader = BiliReader(tmp_path/'a.db', BiliFake())
    packet = await reader.read(BV)
    settings = dict(enabled=True, bili_enabled=True, bili_like_enabled=True,
                    bili_favorite_enabled=True, bili_account_id='42', bili_favorite_folder_id='7')
    backend = Backend()
    actions = BiliActions(reader, settings, backend)
    return actions, packet['reading_id'], backend


async def test_both_actions_verified_then_no_duplicate_even_across_restart(tmp_path):
    a, rid, b = await make(tmp_path)
    for kind in ('like','favorite'):
        assert (await a.apply(rid,kind))['confirmed'] is True
        assert (await a.apply(rid,kind))['state'] == 'already_done'
    assert len(b.calls) == 2
    b.present.clear()  # user undo or eventually-consistent GET must not repeat POST
    restart = BiliActions(a.reader,a.config,b)
    assert (await restart.apply(rid,'favorite'))['state'] == 'not_confirmed_no_retry'
    assert len(b.calls) == 2


async def test_timeout_reserved_and_read_only_reconciliation(tmp_path):
    a,rid,b = await make(tmp_path); b.fail = True
    result = await a.apply(rid,'like')
    assert result['state']=='uncertain' and not result['confirmed']
    assert (await a.apply(rid,'like'))['write_attempted'] is False
    b.present.add(('like',BV,''))
    assert (await a.apply(rid,'like'))['confirmed'] is True
    assert len(b.calls)==1
    assert 'sensitive' not in json.dumps(result)


async def test_post_success_is_not_confirmed_without_readback(tmp_path):
    a,rid,b=await make(tmp_path)
    b.send=AsyncMock(return_value={})
    assert (await a.apply(rid,'favorite'))['state']=='submitted_unverified'
    await a.apply(rid,'favorite');assert b.send.await_count==1


async def test_concurrent_calls_only_one_write(tmp_path):
    a,rid,b=await make(tmp_path)
    results=await asyncio.gather(*(a.apply(rid,'like') for _ in range(5)))
    assert all(x['confirmed'] for x in results) and len(b.calls)==1


async def test_identity_mismatch_and_missing_login_cannot_write(tmp_path):
    a,rid,b=await make(tmp_path)
    b.identity.return_value='99'
    with pytest.raises(CapabilityError):await a.apply(rid,'like')
    b.identity.side_effect=TimeoutError('secret')
    with pytest.raises(CapabilityError,match='未提交'):await a.apply(rid,'favorite')
    assert b.calls==[]


@pytest.mark.parametrize('case',['disabled','global_disabled','no_read','stale','bad_kind','no_folder','bad_state'])
async def test_rejected_before_mutation(tmp_path,case):
    a,rid,b=await make(tmp_path); kind='favorite'
    if case=='disabled':a.config['bili_favorite_enabled']=False
    if case=='global_disabled':a.config['enabled']=False
    if case=='no_read':rid='invented'
    if case=='stale':a.clock=lambda:__import__('time').time()+86401
    if case=='bad_kind':kind='coin'
    if case=='no_folder':a.config['bili_favorite_folder_id']=''
    if case=='bad_state':b.check=AsyncMock(return_value=None)
    with pytest.raises(CapabilityError):await a.apply(rid,kind)
    assert not b.calls


async def test_budget_reserved_for_uncertain_attempts_and_shared_by_instances(tmp_path):
    a,rid,b=await make(tmp_path);a.config['bili_action_daily_limit']=1
    with a.reader.connect() as db:
        db.execute('INSERT INTO bili_actions VALUES(?,?,?,?,?,?)',('42','like','BVdifferent1','',a.clock(),'uncertain'))
    with pytest.raises(CapabilityError,match='预算'):await a.apply(rid,'like')
    assert (await a.apply(rid,'favorite'))['confirmed'] is True
    assert a.status()['attempts_24h']=={'like':1,'favorite':1}


async def test_tool_owner_private_only_and_shelf_not_reused(plugin):
    plugin.config['bili_enabled']=True
    plugin.bili_actions.apply=AsyncMock(return_value={'confirmed':True})
    for e in (Event(private=False),Event(sender='other'),Event(admin=False)):
        assert not json.loads(await plugin.bili_interact(e,'r','like'))['ok']
    e=Event();e.set_extra('fish_public_shelf_read',True)
    assert not json.loads(await plugin.bili_interact(e,'r','like'))['ok']
    plugin.bili_actions.apply.assert_not_called()
    assert json.loads(await plugin.bili_interact(Event(),'r','favorite'))['confirmed']


async def test_sdk_only_adds_to_verified_own_folder(monkeypatch):
    import sys
    v=types.SimpleNamespace(has_liked=AsyncMock(return_value=1),like=AsyncMock(),set_favorite=AsyncMock())
    folders=AsyncMock(return_value={'list':[{'id':7,'mid':42,'fav_state':0}]})
    monkeypatch.setitem(sys.modules,'bilibili_api',types.SimpleNamespace(favorite_list=types.SimpleNamespace(get_video_favorite_list=folders)))
    a=ActionBackend(None);a.video=lambda _:v;a.credential=object()
    assert await a.check('like',BV,'42','') is True
    assert await a.check('favorite',BV,'42','7') is False
    await a.send('like',BV,'');v.like.assert_awaited_once_with(status=True)
    await a.send('favorite',BV,'7');v.set_favorite.assert_awaited_once_with(add_media_ids=[7],del_media_ids=[])
    folders.return_value={'list':[{'id':7,'mid':99,'fav_state':0}]}
    with pytest.raises(CapabilityError):await a.check('favorite',BV,'42','7')


@pytest.mark.parametrize('liked,favorited,expected',[(True,True,2),(False,False,0),('true',1,0)])
async def test_scheduled_choice_controls_optional_actions(tmp_path,liked,favorited,expected):
    from astrbot_plugin_fish_capabilities.services.bili_duty import BiliDuty
    a,rid,b=await make(tmp_path)
    calls=[]
    async def generate(prompt):
        calls.append(prompt)
        return json.dumps({'bvid':BV} if len(calls)==1 else {'bvid':BV,'like':liked,'favorite':favorited,'recommend':False})
    comments=types.SimpleNamespace(post=AsyncMock())
    delivery=AsyncMock()
    result=await BiliDuty(a.reader,comments,a.config,generate,delivery,actions=a).once('slot')
    assert len(b.calls)==expected and len(result['interactions'])==expected
    assert '当前互动开关' in calls[-1]
    delivery.assert_not_called();comments.post.assert_not_called()
    await BiliDuty(a.reader,comments,a.config,generate,delivery,actions=a).once('slot')
    assert len(b.calls)==expected
