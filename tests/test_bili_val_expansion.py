import asyncio,json,sys,time,types
from unittest.mock import AsyncMock
from datetime import datetime
from pathlib import Path
import pytest

from astrbot_plugin_fish_capabilities.services.bili_explore import BiliExplore,ExploreBackend,dynamic_packet
from astrbot_plugin_fish_capabilities.services.bili_activity import BiliActivity
from astrbot_plugin_fish_capabilities.services.bili_actions import BiliActions
from astrbot_plugin_fish_capabilities.services.valorant import ValorantRecords,private_save
from astrbot_plugin_fish_capabilities.services.valorant_insights import query,summary,select,report
from astrbot_plugin_fish_capabilities.services.valorant_shop_notes import ShopNotes,query as shop_query
from astrbot_plugin_fish_capabilities.services.policy import CapabilityError
from test_services import BV,BiliFake
from test_bili_activity import make
from test_bili_actions import make as actions_fixture
from test_valorant_cache_detail import Backend,prepare
from test_astrbot_binding import plugin,Event


def raw_dynamic():
    return {'item':{'id_str':'123','type':'DYNAMIC_TYPE_WORD','modules':{'module_author':{'mid':7,'name':'UP'},'module_dynamic':{'desc':{'text':'公开文字'}}}}}


async def test_explore_bounded_cache_is_partitioned_by_verified_account(tmp_path):
    cfg={'enabled':True,'bili_enabled':True,'bili_explore_enabled':True,'bili_account_id':'42'}
    backend=types.SimpleNamespace(identity=AsyncMock(return_value='42'),read=AsyncMock(return_value=[{'page':1,'part':'第一P','duration':100}]*30))
    service=BiliExplore(None,cfg,backend)
    assert len((await service.query('pages',BV))['items'])==20
    assert (await service.query('pages',BV))['cached']
    assert backend.read.await_count==1
    backend.identity.return_value='other'
    with pytest.raises(CapabilityError):await service.query('pages',BV)
    assert backend.read.await_count==1


@pytest.mark.parametrize('kind',['pages','tags','related','comments','danmaku','dynamic','profile','later','history','folders','favorites'])
async def test_new_reads_are_disabled_by_default(kind):
    backend=types.SimpleNamespace(identity=AsyncMock(),read=AsyncMock())
    with pytest.raises(CapabilityError):await BiliExplore(None,{},backend).query(kind,BV)
    backend.identity.assert_not_called()


def test_dynamic_unavailable_and_wrong_identity_not_repostable():
    data=raw_dynamic();assert dynamic_packet(data,'123')['text']=='公开文字'
    with pytest.raises(CapabilityError):dynamic_packet(data,'124')
    data['item']['visible']=False
    with pytest.raises(CapabilityError):dynamic_packet(data,'123')


async def test_danmaku_sdk_zero_based_segment_is_one_request(monkeypatch):
    v=types.SimpleNamespace(get_danmakus=AsyncMock(return_value=[]))
    sdk=types.ModuleType('bilibili_api');sdk.video=types.SimpleNamespace(Video=lambda **kw:v)
    sdk.user=sdk.comment=sdk.dynamic=sdk.favorite_list=types.SimpleNamespace()
    monkeypatch.setitem(sys.modules,'bilibili_api',sdk)
    backend=ExploreBackend(None)
    await backend.read('danmaku',BV,1)
    v.get_danmakus.assert_awaited_once_with(page_index=0,from_seg=0,to_seg=0)


def test_danmaku_output_is_bounded_deduplicated_and_untrusted():
    raw=[types.SimpleNamespace(text='重复',dm_time=3)]+[types.SimpleNamespace(text='重复',dm_time=4)]+[types.SimpleNamespace(text=str(i),dm_time=i) for i in range(100)]
    out=BiliExplore(None,{},backend=types.SimpleNamespace()).compact('danmaku',BV,raw,1)
    assert len(out['items'])==40 and out['items'][0]['video_seconds']==3
    assert '不是完整' in out['instruction']


async def test_repost_rechecks_source_account_and_shares_dynamic_budget(tmp_path):
    a,b,r,g,n,t,c=make(tmp_path);a.config['bili_repost_enabled']=True
    b.detail=AsyncMock(return_value=dynamic_packet(raw_dynamic(),'123'));b.repost=AsyncMock(return_value='999')
    result=await a.post('这个有点意思',repost_id='123')
    assert result['submitted'] and b.detail.await_count==2
    assert r.gate.call_args.args[1]['repost_id']=='123'
    with pytest.raises(CapabilityError):await a.post('另一条动态')
    b.repost.assert_awaited_once()
    assert a.posts()['items'][0]['url'].endswith('/999')


async def test_repost_source_changed_or_permission_revoked_no_write(tmp_path):
    a,b,r,g,n,t,c=make(tmp_path);a.config['bili_repost_enabled']=True
    original=dynamic_packet(raw_dynamic(),'123')
    b.detail=AsyncMock(side_effect=[original,dict(original,text='改了')]);b.repost=AsyncMock()
    with pytest.raises(CapabilityError):await a.post('公开文字',repost_id='123')
    b.repost.assert_not_called()
    r.gate.side_effect=lambda *args:a.config.update(bili_repost_enabled=False)
    b.detail=AsyncMock(return_value=original)
    with pytest.raises(CapabilityError):await a.post('公开文字',repost_id='123')
    b.repost.assert_not_called()


async def test_repost_uncertain_durable_no_retry_or_text_variation(tmp_path):
    a,b,r,g,n,t,c=make(tmp_path);a.config['bili_repost_enabled']=True
    b.detail=AsyncMock(return_value=dynamic_packet(raw_dynamic(),'123'));b.repost=AsyncMock(side_effect=TimeoutError())
    with pytest.raises(CapabilityError):await a.post('第一句',repost_id='123')
    other=BiliActivity(a.reader,a.config,r,g,n,b,clock=lambda:t[0])
    t[0]+=86400
    with pytest.raises(CapabilityError):await other.post('换个说法',repost_id='123')
    b.repost.assert_awaited_once()


async def test_later_add_is_verified_and_restart_safe(tmp_path):
    a,rid,b=await actions_fixture(tmp_path);a.config['bili_later_enabled']=True
    assert (await a.apply(rid,'later'))['confirmed']
    b.present.clear()
    assert (await BiliActions(a.reader,a.config,b).apply(rid,'later'))['state']=='not_confirmed_no_retry'
    assert len(b.calls)==1


def records():
    return [dict(battle_id=str(i),hero_name='零' if i%2 else '捷风',used_map={'name':'地图A'},game_enum='competitive',
                 result_title='获胜' if i<4 else '未知',kda='10/5/2',score_avg=200+i,ts=1760000000-i*3600) for i in range(12)]


def test_statistics_missing_results_and_mixed_mode_not_invented():
    rows=records();out=summary(rows)
    assert out['known_results']==4 and out['win_rate']==1 and out['kd']==2
    assert summary([dict(rows[0],game_enum='deathmatch'),rows[1]])['average_acs'] is None
    assert summary([dict(rows[0],kda='',score_avg=None)])['kills'] is None


def test_date_filters_use_configured_zone_and_unknown_time_excluded():
    stamp=datetime.fromisoformat('2026-11-06T00:30:00+00:00').timestamp()
    rows=[dict(records()[0],ts=stamp),dict(records()[1],ts=None)]
    filtered,unknown=select(rows,{'local_timezone':'UTC-07:00'},since='2026-11-05',until='2026-11-06')
    assert len(filtered)==1 and unknown==1
    assert not select(rows,{'local_timezone':'UTC+08:00'},since='2026-11-05',until='2026-11-06')[0]


async def test_history_analytics_no_detail_network_and_account_isolation(tmp_path):
    http=Backend();reader=ValorantRecords(prepare(tmp_path),http)
    await reader.profile(30);http.calls.clear()
    out=await query(reader,{},view='history',page=2)
    assert len(out['items'])==10 and not out['has_more']
    assert not any('/record/' in path for path,_ in http.calls)
    private_save(reader.path,{'userId':'new-account','tid':'new-ticket','login_type':'wechat'})
    assert (await query(reader,{}))['sampled_matches']==0


@pytest.mark.parametrize('view',['overview','maps','agents','trend','weapons','teammates'])
async def test_analytics_views_share_captured_sample_without_paid_models(tmp_path,view):
    reader=ValorantRecords(prepare(tmp_path),Backend());await reader.profile(20)
    out=await query(reader,{},view=view)
    assert out['sampled_matches']==20 and out['sync'] is None
    if view in ('weapons','teammates'):assert out['items']==[] and out['detail_matches']==0
    if view=='trend':assert out['recent']['matches']==out['previous']['matches']==10


async def test_cached_teammates_do_not_merge_names_or_fetch_others(tmp_path):
    reader=ValorantRecords(prepare(tmp_path),Backend());await reader.match(1)
    credentials=reader.credentials();role=await reader.role(credentials);account=reader.account(credentials,role)
    board={'scoreboard':[{'is_me':1,'team':'blue','role_id':'owner-role'},
        {'team':'blue','role_id':'a','user_name':'同名','score_avg':200},
        {'team':'blue','role_id':'b','user_name':'同名','score_avg':100}]}
    reader.store.save_detail(account,'0','scoreboard',board)
    out=await query(reader,{},view='teammates')
    assert len(out['items'])==2 and len({x['player_ref'] for x in out['items']})==2
    assert all(x['official_friend_observed'] is False for x in out['items'])


def test_wishlist_explicit_name_role_isolation_and_snapshots(tmp_path):
    reader=ValorantRecords(prepare(tmp_path),Backend());notes=ShopNotes(reader.store)
    with pytest.raises(CapabilityError):notes.change('one','add','狂徒','随便记一个')
    notes.change('one','add','狂徒','帮我记住狂徒')
    assert notes.names('one')==['狂徒'] and notes.names('two')==[]
    packet={'fetched_at':time.time(),'expires_at':123,'items':[{'name':'测试狂徒','price_text':'接口原文'}]}
    notes.capture('one',packet);notes.capture('one',packet)
    assert len(notes.history('one'))==1 and notes.history('two')==[]
    notes.change('one','remove','狂徒','移除狂徒');assert notes.names('one')==[]


async def test_new_tools_private_and_disabled_without_auth(plugin):
    for event in (Event(),Event(private=False),Event(sender='outsider')):
        for tool in (plugin.bili_explore_tool,plugin.valorant_insights,plugin.valorant_shop_notes):
            assert not json.loads(await tool(event))['ok']


async def test_repost_concurrent_instances_reserve_one_public_write(tmp_path):
    a,b,r,g,n,t,c=make(tmp_path);a.config['bili_repost_enabled']=True
    b.detail=AsyncMock(return_value=dynamic_packet(raw_dynamic(),'123'));b.repost=AsyncMock(return_value='999')
    other=BiliActivity(a.reader,a.config,r,g,n,b,clock=lambda:t[0])
    results=await asyncio.gather(a.post('一条',repost_id='123'),other.post('另一条',repost_id='123'),return_exceptions=True)
    assert sum(isinstance(x,dict) and x.get('submitted',False) for x in results)==1
    b.repost.assert_awaited_once()


async def test_repost_account_changed_during_review_does_not_switch_publisher(tmp_path):
    a,b,r,g,n,t,c=make(tmp_path);a.config['bili_repost_enabled']=True
    b.detail=AsyncMock(return_value=dynamic_packet(raw_dynamic(),'123'));b.repost=AsyncMock()
    def change(*args):a.config['bili_account_id']='43';b.who='43'
    r.gate.side_effect=change
    with pytest.raises(CapabilityError):await a.post('公开文字',repost_id='123')
    b.repost.assert_not_called()


async def test_dynamic_image_bytes_and_text_are_jointly_reviewed(tmp_path):
    a,b,r,g,n,t,c=make(tmp_path);a.config['bili_dynamic_image_enabled']=True
    image=types.SimpleNamespace(sha256='fixture-sha',description='公开图',image_text='你好',path=Path('fixture.png'))
    a.media=types.SimpleNamespace(image=lambda ident:image,library=types.SimpleNamespace(bytes_for=lambda m:b'fixture-image'))
    b.post_image=AsyncMock(return_value='999')
    assert (await a.post('今天很开心',meme_id='approved-id'))['submitted']
    assert r.gate.call_args.args[3]['image']['image_text']=='你好'
    b.post_image.assert_awaited_once_with('今天很开心',b'fixture-image','png')


async def test_dynamic_image_changed_during_review_or_arbitrary_path_no_write(tmp_path):
    a,b,r,g,n,t,c=make(tmp_path);a.config['bili_dynamic_image_enabled']=True
    image=types.SimpleNamespace(sha256='old',description='公开图',image_text='你好',path=Path('fixture.png'))
    a.media=types.SimpleNamespace(image=lambda ident:image,library=types.SimpleNamespace(bytes_for=lambda m:b'old'))
    b.post_image=AsyncMock()
    r.gate.side_effect=lambda *args:setattr(a.media,'image',lambda ident:types.SimpleNamespace(sha256='new'))
    with pytest.raises(CapabilityError):await a.post('看看',meme_id='approved-id')
    b.post_image.assert_not_called()
    a.config['bili_dynamic_image_enabled']=False
    with pytest.raises(CapabilityError):await a.post('看看',meme_id='C:/private.png')
    b.post_image.assert_not_called()


async def test_later_brain_deferral_releases_only_pre_send_reservation(tmp_path):
    from astrbot_plugin_fish_capabilities.services.brain import AttentionDeferred
    a,rid,b=await actions_fixture(tmp_path);a.config['bili_later_enabled']=True
    b.send=AsyncMock(side_effect=AttentionDeferred('globally_muted'))
    with pytest.raises(AttentionDeferred):await a.apply(rid,'later')
    with a.reader.connect() as db:assert db.execute('SELECT COUNT(*) FROM bili_actions').fetchone()[0]==0


async def test_later_revoked_during_status_check_no_mutation(tmp_path):
    a,rid,b=await actions_fixture(tmp_path);a.config['bili_later_enabled']=True
    async def check(*args):a.config['bili_later_enabled']=False;return False
    b.check=check
    with pytest.raises(CapabilityError):await a.apply(rid,'later')
    assert b.calls==[]


async def test_own_favorite_folder_is_checked_before_contents(monkeypatch):
    sdk=types.ModuleType('bilibili_api')
    folders=AsyncMock(return_value={'list':[{'id':7,'mid':42,'title':'我的夹'}]})
    content=AsyncMock(return_value={'info':{'id':7,'upper':{'mid':42}},'medias':[]})
    sdk.favorite_list=types.SimpleNamespace(get_video_favorite_list=folders,get_video_favorite_list_content=content)
    sdk.video=sdk.user=sdk.comment=sdk.dynamic=types.SimpleNamespace()
    monkeypatch.setitem(sys.modules,'bilibili_api',sdk)
    backend=ExploreBackend(None);backend.account='42'
    with pytest.raises(CapabilityError):await backend.read('favorites','8',1)
    content.assert_not_called()
    assert (await backend.read('favorites','7',1))['list']==[]
    content.return_value={'info':{'id':7,'upper':{'mid':99}},'medias':[]}
    with pytest.raises(CapabilityError):await backend.read('favorites','7',1)


async def test_follow_add_only_account_checked_and_no_retry_after_undo(tmp_path):
    a,rid,b=await actions_fixture(tmp_path)
    with pytest.raises(CapabilityError):await a.follow('7')
    a.config['bili_follow_enabled']=True
    assert (await a.follow('7'))['confirmed']
    assert (await a.follow('7'))['state']=='already_done'
    b.present.clear()
    assert (await BiliActions(a.reader,a.config,b).follow('7'))['state']=='not_confirmed_no_retry'
    assert b.calls==[('follow','7','')]
    with pytest.raises(CapabilityError):await a.follow('42')


async def test_follow_status_unknown_or_account_mismatch_never_writes(tmp_path):
    a,rid,b=await actions_fixture(tmp_path);a.config['bili_follow_enabled']=True
    b.check=AsyncMock(return_value=None)
    with pytest.raises(CapabilityError):await a.follow('7')
    b.identity.return_value='43'
    with pytest.raises(CapabilityError):await a.follow('7')
    assert not b.calls


async def test_shop_check_records_actual_result_and_wishlist_does_not_purchase(tmp_path):
    class ShopBackend(Backend):
        async def post(self,path,data,auth=None):
            if path=='/go/mlol_store/agame/user_store':
                self.calls.append((path,data));return {'result':0,'data':{'key':'dailystore','list':[{'goods_name':'测试狂徒','rmb_price':'接口价格'}],'end_ts':time.time()+600}}
            return await super().post(path,data,auth)
    backend=ShopBackend();reader=ValorantRecords(prepare(tmp_path),backend)
    await shop_query(reader,'add','狂徒','把狂徒加入愿望单')
    result=await shop_query(reader,'check')
    assert [x['name'] for x in result['matches']]==['测试狂徒']
    assert result['matches'][0]['price_text']=='接口价格'
    assert len((await shop_query(reader,'history'))['history'])==1
    assert all(path in ('/go/account/get_main_role_raw','/go/mlol_store/agame/user_store') for path,_ in backend.calls)


async def test_analytics_invalid_page_precedes_credential_read(tmp_path):
    reader=types.SimpleNamespace(credentials=AsyncMock())
    with pytest.raises(CapabilityError):await query(reader,{},page=0)
    reader.credentials.assert_not_called()


async def test_transport_rechecks_after_brain_queue_without_sdk_call(tmp_path,monkeypatch):
    from astrbot_plugin_fish_capabilities.services.bili_activity import ActivityBackend
    from astrbot_plugin_fish_capabilities.services.bili_actions import ActionBackend
    from astrbot_plugin_fish_capabilities.services.brain import AttentionDeferred
    a,b,r,g,n,t,c=make(tmp_path)
    transport=ActivityBackend(None);transport.bound_account='42'
    runtime=BiliActivity(a.reader,a.config,r,g,n,transport,clock=lambda:t[0])
    a.config['bili_dynamic_post_enabled']=False
    with pytest.raises(AttentionDeferred):await transport.post('不会调用SDK')
    actions=BiliActions(a.reader,dict(enabled=True,bili_enabled=True,bili_like_enabled=False,bili_account_id='42'),ActionBackend(None))
    actions.backend.bound_account='42'
    with pytest.raises(AttentionDeferred):await actions.backend.send('like',BV,'')


async def test_approved_dynamic_payload_roundtrip_preserves_image_hash(tmp_path):
    a,b,r,g,n,t,c=make(tmp_path);a.config['bili_dynamic_image_enabled']=True
    image=types.SimpleNamespace(sha256='old-image',description='公开图',image_text='你好',path=Path('fixture.png'))
    a.media=types.SimpleNamespace(image=lambda ident:image,library=types.SimpleNamespace(bytes_for=lambda m:b'fixture'))
    b.post_image=AsyncMock(return_value='999');r.gate.side_effect=CapabilityError('pending review')
    with pytest.raises(CapabilityError):await a.post('公开文字',meme_id='approved')
    payload=r.gate.call_args.args[1]
    assert payload['image_sha256']=='old-image'
    r.gate.side_effect=None
    assert (await a.post('公开文字',**payload))['submitted']


async def test_approved_repost_payload_rejects_later_source_changes(tmp_path):
    a,b,r,g,n,t,c=make(tmp_path);a.config['bili_repost_enabled']=True
    original=dynamic_packet(raw_dynamic(),'123')
    b.detail=AsyncMock(return_value=original);b.repost=AsyncMock(return_value='999')
    r.gate.side_effect=CapabilityError('pending review')
    with pytest.raises(CapabilityError):await a.post('公开文字',repost_id='123')
    payload=r.gate.call_args.args[1];assert payload['repost_fingerprint']
    r.gate.side_effect=None;b.detail.return_value=dict(original,text='改过的内容')
    with pytest.raises(CapabilityError):await a.post('公开文字',**payload)
    b.repost.assert_not_called()
    b.detail.return_value=original
    assert (await a.post('公开文字',**payload))['submitted']
