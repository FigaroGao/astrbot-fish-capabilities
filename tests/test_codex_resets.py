import copy
import json
from datetime import datetime,timezone

import pytest
from astrbot_plugin_fish_capabilities.services.codex_resets import CodexResets,announcement
from astrbot_plugin_fish_capabilities.services.policy import Actor,CapabilityError
from astrbot_plugin_fish_capabilities.services.capability_registry import authorize

NOW=datetime(2026,10,27,12,tzinfo=timezone.utc).timestamp()


def packet(ident='old',at='2026-10-26T07:00:00Z'):
    return {'data':{'latest_reset':{'id':ident,'announced_at':at,'reset_type':'regular','text':'公开重置公告',
                                  'source':{'type':'x_post','url':'https://x.com/thsottiaux/status/123'}}},
            'meta':{'live':True,'stale':False,'synced_at':'2026-10-27T12:00:00Z','source_error':None}}


class Transport:
    def __init__(self):self.data=packet();self.calls=[];self.fail=False
    async def get(self,url,hosts):
        self.calls.append((url,hosts))
        if self.fail:raise RuntimeError('remote unavailable')
        return copy.deepcopy(self.data)


async def test_status_conversion_cache_and_no_personal_claim(tmp_path):
    http=Transport();t=[NOW];service=CodexResets(tmp_path/'state.db',http,lambda:t[0])
    a=await service.status();await service.status()
    assert len(http.calls)==1 and a['sync_fresh']
    assert a['latest_reset']['announced_at_hk']=='2026-10-26T15:00:00+08:00'
    assert not a['personal_account_checked'] and not a['official_openai_service']
    assert a['next_reset_prediction'] is None
    assert http.calls[0][1]=={'codex.markets'} and 'lang=zh-Hans' in http.calls[0][0]


async def test_stale_failure_negative_cache_no_notification(tmp_path):
    http=Transport();t=[NOW];service=CodexResets(tmp_path/'state.db',http,lambda:t[0])
    await service.status();http.fail=True;t[0]+=901
    result=await service.status()
    assert result['stale'] and result['fetch_failed']
    assert (await service.poll(lambda x:None))['state']=='stale_or_empty'
    assert len(http.calls)==2


async def test_only_newer_new_id_once_and_restart_baseline(tmp_path):
    http=Transport();t=[NOW];sent=[]
    async def deliver(text):sent.append(text)
    service=CodexResets(tmp_path/'state.db',http,lambda:t[0])
    assert (await service.poll(deliver))['state']=='baseline_saved'
    http.data=packet('new','2026-10-27T11:00:00Z');t[0]+=901
    assert (await service.poll(deliver))['sent']
    assert not (await service.poll(deliver))['sent']
    restarted=CodexResets(tmp_path/'state.db',http,lambda:t[0])
    assert not (await restarted.poll(deliver))['sent'] and len(sent)==1
    assert '还没有核对' in sent[0] and '个人账号' in sent[0]


async def test_stale_sync_and_old_announcements_never_new_reset(tmp_path):
    http=Transport();t=[NOW];sent=[]
    async def deliver(text):sent.append(text)
    service=CodexResets(tmp_path/'state.db',http,lambda:t[0]);await service.poll(deliver)
    t[0]+=901;http.data=packet('backfill','2026-10-25T07:00:00Z')
    assert (await service.poll(deliver))['state']=='unchanged'
    t[0]+=901;http.data=packet('new','2026-10-27T11:00:00Z');http.data['meta']['stale']=True
    assert (await service.poll(deliver))['state']=='stale_or_empty'
    assert not sent


async def test_uncertain_delivery_not_repeated(tmp_path):
    http=Transport();t=[NOW]
    service=CodexResets(tmp_path/'state.db',http,lambda:t[0])
    async def deliver(text):raise RuntimeError('unknown receipt')
    await service.poll(deliver);t[0]+=901;http.data=packet('new','2026-10-27T11:00:00Z')
    with pytest.raises(RuntimeError):await service.poll(deliver)
    assert not (await service.poll(deliver))['sent']
    with service.db() as db:assert db.execute("SELECT state FROM notices WHERE id='new'").fetchone()[0]=='uncertain'


async def test_history_cursor_and_detail_validation(tmp_path):
    http=Transport();service=CodexResets(tmp_path/'state.db',http,lambda:NOW)
    row=packet()['data']['latest_reset']
    http.data={'data':[row],'meta':packet()['meta'],'pagination':{'has_more':True,'next_cursor':'time|id'}}
    result=await service.history(1,'a|b')
    assert result['next_cursor']=='time|id' and 'cursor=a%7Cb' in http.calls[0][0]
    http.data={'data':row,'meta':packet()['meta']}
    assert (await service.detail('old'))['announcement']['id']=='old'
    for value in ['../status','https://evil.example','a/b']:
        with pytest.raises(CapabilityError):await service.detail(value)
    with pytest.raises(CapabilityError):await service.history(True)


def test_untrusted_source_url_not_forwarded():
    row=packet()['data']['latest_reset'];row['source']['url']='https://x.com:bad/account'
    assert announcement(row)['source']['url']==''


def test_owner_private_registry_permission():
    config={'enabled':True,'codex_resets_enabled':True,'owners':['owner'],'command_platform_ids':['qq']}
    assert authorize(config,Actor('owner','qq',True,True),'codex_resets')
    for actor in [Actor('owner','qq',False,True,'7'),Actor('other','qq',True,True),Actor('owner','other',True,True)]:
        with pytest.raises(CapabilityError):authorize(config,actor,'codex_resets')


async def test_future_announcement_is_not_completed_reset(tmp_path):
    http=Transport();http.data=packet('future','2026-10-28T12:00:00Z')
    service=CodexResets(tmp_path/'state.db',http,lambda:NOW)
    assert (await service.poll(lambda _:None))['state']=='future_announcement_rejected'
