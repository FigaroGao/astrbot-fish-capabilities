import json,sys,types
from unittest.mock import AsyncMock
import pytest
from astrbot_plugin_fish_capabilities.services.bili_social import BiliSocial
from astrbot_plugin_fish_capabilities.services.bili_comments import CommentBackend
from astrbot_plugin_fish_capabilities.services.policy import CapabilityError
from test_bili_comments import prepared,Posting
from test_astrbot_binding import plugin,Event
from test_services import BV

class SocialFake:
    def __init__(self,account='42'):self.account=account;self.video_calls=0
    async def following(self,page,limit):return self.account,{'list':[{'mid':123,'uname':'owner','attribute':6}],'total':1}
    async def videos(self,uid,limit):
        self.video_calls+=1
        return {'list':{'vlist':[{'bvid':BV,'title':'short','length':'00:34','created':123456,'play':12,'author':'owner'}, {'bvid':'BV1234567890','length':'11:00'}]}}

async def test_following_and_owner_public_uploads_are_bounded_and_cached(tmp_path):
    reader,p,w=await prepared(tmp_path);backend=SocialFake();social=BiliSocial(reader,dict(w.settings,bili_owner_uid='123'),backend)
    f=await social.following();assert f['followings'][0]['mutual'] and f['followings'][0]['is_bound_owner']
    videos=await social.videos();assert len(videos['videos'])==1
    assert videos['videos'][0]['duration']==34 and videos['videos'][0]['published_at']==123456 and videos['videos'][0]['views']==12
    assert (await social.videos())['cached'] and backend.video_calls==1
    backend.account='99'
    with pytest.raises(CapabilityError):await social.following()
    with pytest.raises(CapabilityError):await social.videos('not-a-uid')

class Mentions(Posting):
    def __init__(self):super().__init__();self.sent=None
    async def prepare_mention(self,uid):return {'uid':uid,'name':'owner'}
    async def send(self,video_id,text,mention=None):self.calls+=1;self.sent=(text,mention);return {'reply_id':'123','aid':456}

async def test_owner_only_mention_one_mapping_and_anonymous_visibility_distinct(tmp_path):
    backend=Mentions();backend.verify_public=AsyncMock(return_value=None)
    _,p,w=await prepared(tmp_path,backend);w.settings.update(bili_owner_uid='123',bili_owner_mention_enabled=True)
    result=await w.post(p['reading_id'],'有意思。',[p['evidence'][0]['evidence_id']],mention_owner=True)
    assert backend.sent==('有意思。 @owner',{'uid':'123','name':'owner'}) and backend.calls==1
    assert result['submitted'] and result['mention_submitted'] and result['author_visible_verified']
    assert not result['publicly_visible_verified'] and not result['notification_received_verified']
    assert result['visibility_status']=='author_read_only'


@pytest.mark.parametrize('text,expected',[
    ('{{owner}} 这段你可能喜欢。','@owner 这段你可能喜欢。'),
    ('看到这段想到你，{{owner}}来看看。','看到这段想到你， @owner 来看看。'),
    ('这段挺有意思 {{owner}}','这段挺有意思 @owner'),
])
async def test_marker_places_verified_mention_anywhere(tmp_path,text,expected):
    backend=Mentions();_,p,w=await prepared(tmp_path,backend)
    w.settings.update(bili_owner_uid='123',bili_owner_mention_enabled=True)
    result=await w.post(p['reading_id'],text,[p['evidence'][0]['evidence_id']],True)
    assert backend.sent==(expected,{'uid':'123','name':'owner'})
    assert result['mention_submitted'] and not result['notification_received_verified']
    assert backend.sent[0].count('@')==1 and '{{owner}}' not in backend.sent[0]


async def test_ordinary_comment_needs_no_mention_or_owner_lookup(tmp_path):
    backend=Mentions();backend.prepare_mention=AsyncMock()
    _,p,w=await prepared(tmp_path,backend)
    result=await w.post(p['reading_id'],'这个细节挺有意思。',[p['evidence'][0]['evidence_id']])
    assert backend.sent==('这个细节挺有意思。',None)
    assert not result['mention_submitted'];backend.prepare_mention.assert_not_called()


@pytest.mark.parametrize('text,enabled',[
    ('{{owner}} 看看 {{owner}}',True),
    ('{{owner}} 看看',False),
    ('{{owner}} @other 看看',True),
    ('{{owner}} ＠other 看看',True),
])
async def test_invalid_marker_combinations_never_post(tmp_path,text,enabled):
    backend=Mentions();_,p,w=await prepared(tmp_path,backend)
    w.settings.update(bili_owner_uid='123',bili_owner_mention_enabled=True)
    with pytest.raises(CapabilityError):
        await w.post(p['reading_id'],text,[p['evidence'][0]['evidence_id']],enabled)
    assert backend.calls==0


async def test_expanded_verified_nickname_still_obeys_final_length(tmp_path):
    backend=Mentions();backend.prepare_mention=AsyncMock(return_value={'uid':'123','name':'n'*60})
    _,p,w=await prepared(tmp_path,backend)
    w.settings.update(bili_owner_uid='123',bili_owner_mention_enabled=True)
    with pytest.raises(CapabilityError,match='220'):
        await w.post(p['reading_id'],'文'*210+'{{owner}}',[p['evidence'][0]['evidence_id']],True)
    assert backend.calls==0


@pytest.mark.parametrize('choice,expected',[(True,True),(False,False),('true',False)])
async def test_scheduled_comment_can_choose_mention_but_never_requires_it(tmp_path,choice,expected):
    from astrbot_plugin_fish_capabilities.services.bili_duty import BiliDuty
    reader,p,w=await prepared(tmp_path)
    w.settings['bili_owner_mention_enabled']=True
    writer=types.SimpleNamespace(post=AsyncMock(return_value={'submitted':True}))
    prompts=[]
    async def generate(prompt):
        prompts.append(prompt)
        return json.dumps({'bvid':BV} if len(prompts)==1 else {'bvid':BV,'comment':'一个具体感受。','mention_owner':choice,'evidence_ids':[p['evidence'][0]['evidence_id']]})
    await BiliDuty(reader,writer,w.settings,generate,AsyncMock()).once('optional-mention')
    assert writer.post.await_count==1
    assert writer.post.call_args.kwargs==({'mention_owner':True} if expected else {})
    assert '默认false' in prompts[-1] and '{{owner}}' in prompts[-1]

@pytest.mark.parametrize('case',['disabled','manual_other_at','uid_mismatch'])
async def test_bad_mention_never_posts(tmp_path,case):
    backend=Mentions();_,p,w=await prepared(tmp_path,backend)
    w.settings.update(bili_owner_uid='123',bili_owner_mention_enabled=True);text='内容'
    if case=='disabled':w.settings['bili_owner_mention_enabled']=False
    if case=='manual_other_at':text='内容 @other'
    if case=='uid_mismatch':backend.prepare_mention=AsyncMock(return_value={'uid':'999','name':'other'})
    with pytest.raises(CapabilityError):await w.post(p['reading_id'],text,[p['evidence'][0]['evidence_id']],True)
    assert backend.calls==0

async def test_anonymous_public_reader_requires_exact_id_author_and_text(monkeypatch):
    calls=[]
    class Public:
        async def get(self,url,hosts):
            calls.append((url,hosts))
            return {'code':0,'data':{'replies':[{'rpid':'123','member':{'mid':'42'},'content':{'message':'text'}}]}}
    monkeypatch.setattr('astrbot_plugin_fish_capabilities.services.bili_comments.PublicJSON',Public)
    backend=CommentBackend(None)
    assert await backend.verify_public(456,'123','42','text') is True
    assert await backend.verify_public(456,'123','42','different') is False
    assert all(hosts=={'api.bilibili.com'} and 'sess' not in url.lower() for url,hosts in calls)

async def test_comment_mention_transport_payload_without_network(monkeypatch):
    captured={}
    class API:
        def __init__(self,**kwargs):captured['api']=kwargs
        def update_data(self,**kwargs):captured['data']=kwargs;return self
        @property
        def result(self):
            async def done():return {'rpid':123}
            return done()
    module=types.ModuleType('bilibili_api');module.comment=types.SimpleNamespace(API={'comment':{'send':{'url':'https://api.bilibili.com/x/v2/reply/add','method':'POST'}}})
    network=types.ModuleType('bilibili_api.utils.network');network.Api=API
    monkeypatch.setitem(sys.modules,'bilibili_api',module);monkeypatch.setitem(sys.modules,'bilibili_api.utils.network',network)
    backend=CommentBackend(types.SimpleNamespace(credential=lambda:'synthetic-credential',info=AsyncMock(return_value={'aid':456})))
    result=await backend.send(BV,'text @owner',{'uid':'123','name':'owner'})
    assert json.loads(captured['data']['at_name_to_mid'])=={'owner':123}
    assert captured['data']['message']=='text @owner' and result['mention_submitted']

async def test_discovery_and_mentions_stay_private_owner_only(plugin):
    plugin.config['bili_enabled']=True
    plugin.bili_social.following=AsyncMock();plugin.bili_social.videos=AsyncMock()
    for event in [Event(private=False),Event(sender='other',admin=False)]:
        assert json.loads(await plugin.bili_followings(event))['ok'] is False
        assert json.loads(await plugin.bili_up_videos(event))['ok'] is False
    plugin.bili_social.following.assert_not_awaited();plugin.bili_social.videos.assert_not_awaited()
