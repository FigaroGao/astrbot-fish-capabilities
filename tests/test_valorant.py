import json
from unittest.mock import AsyncMock
import pytest
from astrbot_plugin_fish_capabilities.services.policy import CapabilityError
from astrbot_plugin_fish_capabilities.services.valorant import MvalHTTP,ValorantRecords,WeChatLogin,cookie,parse_poll,private_save
from test_astrbot_binding import plugin,Event


def test_wechat_poll_parses_protocol_without_executing_scripts():
    assert parse_poll("window.wx_errcode=405;window.wx_code='synthetic-code';throw 123;")=={'wx_errcode':405,'wx_code':'synthetic-code'}
    assert parse_poll('{"wx_errcode":408}')=={'wx_errcode':408}
    with pytest.raises(CapabilityError):parse_poll('unknown response')


@pytest.mark.parametrize('bad',['x\r\nCookie: wrong','x; other=wrong',''])
def test_cookie_header_injection_and_missing_credentials_rejected(bad):
    with pytest.raises(CapabilityError):cookie({'userId':'synthetic','tid':bad})


def test_credentials_cannot_be_sent_to_wechat_or_arbitrary_host(monkeypatch):
    opened=[]
    monkeypatch.setattr('urllib.request.build_opener',lambda *a:opened.append(a))
    for url in ['https://evil.example/go/auth/login_by_wechat','http://app.mval.qq.com/go/account/get_main_role_raw',
                'https://open.weixin.qq.com/connect/sdk/qrconnect','https://app.mval.qq.com/unreviewed-path']:
        with pytest.raises(CapabilityError):MvalHTTP().request(url,auth={'userId':'synthetic','tid':'secret-value'})
    assert opened==[]


class Fake:
    def __init__(self,roles=1):self.calls=[];self.roles=roles
    async def post(self,path,data,auth=None):
        self.calls.append((path,data,auth))
        if path=='/go/account/get_main_role_raw':
            return {'result':0,'data':{'list':[{'game_role_id':'synthetic-role','scene':'secret-scene','role_name':'test owner','tier_text':'rank'}]*self.roles}}
        if path=='/go/agame/career/record/list':
            return {'result':0,'data':{'battle_list':[{'result_title':'获胜','hero_name':'零','kda':'10/5/4','score_avg':'200','used_map':{'name':'裂变峡谷'},'openid':'secret-openid'}]*5}}
        raise AssertionError(path)


async def test_records_are_bounded_cached_and_do_not_return_auth(tmp_path):
    p=tmp_path/'creds.json';private_save(p,{'userId':'synthetic','tid':'secret-value','login_type':'wechat'})
    http=Fake();reader=ValorantRecords(p,http)
    first=await reader.read(3);second=await reader.read(5)
    assert len(first['matches'])==3 and len(second['matches'])==5 and second['cached']
    assert len(http.calls)==2
    assert 'secret-' not in json.dumps(first) and 'secret-' not in json.dumps(second)
    private_save(p,{'userId':'other-synthetic','tid':'different','login_type':'wechat'})
    await reader.read(3)
    assert len(http.calls)==4
    with pytest.raises(CapabilityError):await reader.read(6)


async def test_multiple_roles_are_not_silently_selected(tmp_path):
    http=Fake(roles=2);reader=ValorantRecords(tmp_path/'not-used',http)
    with pytest.raises(CapabilityError):await reader.role({'userId':'synthetic','tid':'secret'})
    assert len(http.calls)==1


async def test_binding_rejects_non_wechat_and_unbound_accounts(tmp_path):
    p=tmp_path/'creds.json';reader=ValorantRecords(p,Fake())
    with pytest.raises(CapabilityError):await reader.read()
    private_save(p,{'userId':'synthetic','tid':'secret','login_type':'qq'})
    with pytest.raises(CapabilityError):await reader.read()


async def test_game_records_only_owner_private_and_are_off_until_bound(plugin):
    plugin.valorant_records.read=AsyncMock(return_value={'matches':[]})
    assert json.loads(await plugin.valorant_recent(Event()))['ok'] is False
    plugin.config['valorant_enabled']=True
    assert json.loads(await plugin.valorant_recent(Event(private=False)))['ok'] is False
    assert json.loads(await plugin.valorant_recent(Event(sender='other',admin=False)))['ok'] is False
    plugin.valorant_records.read.assert_not_awaited()
    assert json.loads(await plugin.valorant_recent(Event()))=={'matches':[]}
    plugin.valorant_records.read.assert_awaited_once_with(3)


async def test_exchange_does_not_accept_missing_or_rejected_credentials():
    http=type('HTTP',(),{'post':AsyncMock(return_value={'result':1,'data':{'login_info':{'user_id':'synthetic','wt':'secret'}}})})()
    with pytest.raises(CapabilityError):await WeChatLogin(http).exchange('synthetic-code')
    http.post.return_value={'result':0,'data':{'login_info':{'result':0,'user_id':'synthetic','wt':'secret'}}}
    result=await WeChatLogin(http).exchange('synthetic-code')
    assert result['login_type']=='wechat' and result['tid']=='secret'


@pytest.mark.parametrize('raw',[b'\xff\xd8\xffsynthetic\xff\xd9',b'\x89PNG\r\n\x1a\nsynthetic'])
async def test_qr_accepts_both_official_image_formats(raw):
    import base64
    http=type('HTTP',(),{'post':AsyncMock(return_value={'data':{'ticket':'synthetic-ticket'}}),
        'request':lambda self,url:{'errcode':0,'uuid':'synthetic-uuid','qrcode':{'qrcodebase64':base64.b64encode(raw).decode()}}})()
    assert (await WeChatLogin(http).generate())['image']==raw


async def test_qr_rejects_non_image_payload():
    import base64
    http=type('HTTP',(),{'post':AsyncMock(return_value={'data':{'ticket':'synthetic-ticket'}}),
        'request':lambda self,url:{'errcode':0,'uuid':'synthetic-uuid','qrcode':{'qrcodebase64':base64.b64encode(b'<html>wrong</html>').decode()}}})()
    with pytest.raises(CapabilityError):await WeChatLogin(http).generate()


@pytest.mark.parametrize('wrapped',[False,True])
def test_only_wechat_poll_timeout_is_waiting_not_failed_login(monkeypatch,wrapped):
    import urllib.error
    calls=[]
    class Opener:
        def open(self,request,timeout):
            calls.append(timeout)
            error=TimeoutError('synthetic timeout with private data never logged')
            if wrapped:raise urllib.error.URLError(error)
            raise error
    monkeypatch.setattr('urllib.request.build_opener',lambda *a:Opener())
    http=MvalHTTP()
    assert http.request('https://long.open.weixin.qq.com/connect/l/qrconnect?f=json&uuid=synthetic')=={'wx_errcode':408,'local_wait_timeout':True}
    assert calls==[35]
    with pytest.raises(CapabilityError):http.request('https://app.mval.qq.com/go/auth/login_by_wechat',{})
    assert calls==[35,15]


async def test_poll_sends_previous_status_without_exposing_auth():
    from urllib.parse import urlsplit,parse_qs
    urls=[]
    class HTTP:
        def request(self,url):urls.append(url);return {'wx_errcode':408}
    assert (await WeChatLogin(HTTP()).poll('synthetic-uuid',404))['wx_errcode']==408
    assert parse_qs(urlsplit(urls[0]).query)=={'f':['json'],'uuid':['synthetic-uuid'],'last':['404']}


async def test_profile_paginates_and_aggregates_only_real_kda_with_cache(tmp_path):
    class Pages(Fake):
        async def post(self,path,data,auth=None):
            if path!='/go/agame/career/record/list':return await super().post(path,data,auth)
            self.calls.append((path,data,auth))
            page=data['page_no']
            return {'result':0,'data':{'next_baton':'synthetic-baton' if page==1 else '', 'battle_list':[
                {'battle_id':str(page)+'-'+str(i),'hero_name':'零' if page==1 else '雷兹','kda':'20/10/5' if i<9 else 'unknown',
                 'result_title':'获胜' if page==1 else '失败','game_mode':'竞技模式','score_avg':'200','scene':'secret-scene'} for i in range(10)]}}
    p=tmp_path/'c.json';private_save(p,{'userId':'synthetic','tid':'secret-value','login_type':'wechat'})
    http=Pages();r=ValorantRecords(p,http)
    result=await r.profile(20)
    assert result['sampled_matches']==20 and result['kda_valid_matches']==18
    assert result['kd']==2 and result['kills']==360 and result['deaths']==180
    assert result['win_rate_excluding_draws']==.5
    assert result['most_used_agents']==[{'agent':'零','matches':10},{'agent':'雷兹','matches':10}]
    assert len(result['recent_matches'])==3 and 'secret-' not in json.dumps(result)
    assert (await r.profile(20))['cached'] and len(http.calls)==3
    assert http.calls[-1][1]['baton']=='synthetic-baton'


async def test_profile_repeated_page_stops_and_zero_deaths_not_infinity(tmp_path):
    class Repeated(Fake):
        async def post(self,path,data,auth=None):
            if path!='/go/agame/career/record/list':return await super().post(path,data,auth)
            self.calls.append((path,data,auth))
            return {'result':0,'data':{'battle_list':[{'battle_id':str(i),'kda':'1/0/2'} for i in range(10)]}}
    p=tmp_path/'c.json';private_save(p,{'userId':'synthetic','tid':'secret-value','login_type':'wechat'})
    http=Repeated();r=ValorantRecords(p,http);result=await r.profile(30,mode='all')
    assert result['sampled_matches']==10 and result['kd'] is None
    assert result['win_rate_excluding_draws'] is None and len(http.calls)==3
    with pytest.raises(CapabilityError):await r.profile(31)


async def test_profile_tool_owner_private_only(plugin):
    plugin.config['valorant_enabled']=True;plugin.valorant_records.profile=AsyncMock(return_value={'sampled_matches':20})
    assert json.loads(await plugin.valorant_profile(Event(private=False)))['ok'] is False
    assert json.loads(await plugin.valorant_profile(Event(sender='other',admin=False)))['ok'] is False
    plugin.valorant_records.profile.assert_not_awaited()
    assert json.loads(await plugin.valorant_profile(Event()))['sampled_matches']==20
