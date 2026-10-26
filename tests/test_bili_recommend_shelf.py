import json,sys,types
from unittest.mock import AsyncMock
import pytest
from astrbot_plugin_fish_capabilities.services.bilibili import BiliReader,BiliBackend
from astrbot_plugin_fish_capabilities.services.bili_shelf import PublicShelf,shelf_requested
from astrbot_plugin_fish_capabilities.services.policy import CapabilityError
from test_services import BiliFake,BV
from test_astrbot_binding import plugin,Event

class Feed(BiliFake):
    def __init__(self):super().__init__();self.calls=[]
    async def recommend(self,limit):self.calls.append('recommended');return [{'bvid':BV,'duration':60,'title':'首页'}, {'bvid':BV,'duration':60}]
    async def feed(self,limit):self.calls.append('popular');return [{'bvid':BV,'duration':60}]
    async def search(self,key,limit):self.calls.append('search');return [{'bvid':BV,'duration':60}]

async def test_homepage_default_explicit_search_and_popular_never_mislabeled(tmp_path):
    backend=Feed();reader=BiliReader(tmp_path/'b.db',backend,recommendation_enabled=True)
    assert (await reader.browse())['mode']=='account_homepage'
    assert len((await reader.browse())['videos'])==1
    assert (await reader.browse('鲸鱼'))['mode']=='search'
    assert (await reader.browse(source='popular'))['mode']=='public_popular'
    assert backend.calls==['recommended','recommended','search','popular']
    backend.recommend=AsyncMock(side_effect=TimeoutError())
    with pytest.raises(CapabilityError):await reader.browse()
    assert backend.calls[-1]=='popular'  # failure does not silently call popular again

async def test_recommend_uses_logged_account_and_excludes_ads(monkeypatch):
    calls=[]
    credential=types.SimpleNamespace(dedeuserid='42',raise_for_no_sessdata=lambda:None)
    async def homepage(credential):calls.append(credential);return {'mid':42,'item':[{'goto':'av','bvid':BV},{'goto':'live','bvid':'not-video'},{'goto':'av','bvid':'ad','business_info':{'ad':True}}]}
    module=types.ModuleType('bilibili_api');module.homepage=types.SimpleNamespace(get_videos=homepage)
    monkeypatch.setitem(sys.modules,'bilibili_api',module)
    backend=BiliBackend();backend.credential=lambda:credential
    assert await backend.recommend(20)==[{'goto':'av','bvid':BV}] and calls==[credential]
    credential.dedeuserid='99'
    with pytest.raises(CapabilityError):await backend.recommend(20)

class Shelf:
    def __init__(self):self.content_calls=[]
    async def likes(self,owner):return [{'bvid':BV,'title':'title','duration':120,'owner':{'name':'UP'},'fav_time':123,'like_time':456,'pubdate':789}]
    async def folders(self,owner):return {'list':[{'id':1,'mid':owner,'attr':0,'title':'public','ctime':999},{'id':2,'mid':owner,'attr':1,'title':'private'},{'id':3,'mid':owner,'title':'unknown privacy'}]}
    async def content(self,folder,page):
        self.content_calls.append((folder,page));return {'info':{'id':int(folder),'mid':'123','attr':0},'medias':[{'bvid':BV,'title':'video','duration':60,'upper':{'name':'UP'},'fav_time':999}],'has_more':False}

async def test_shelf_strips_times_filters_private_and_has_no_memory_sink():
    backend=Shelf();shelf=PublicShelf({'bili_owner_uid':'123'},backend)
    likes=await shelf.read('likes');assert set(likes['videos'][0])=={'bvid','title','author','duration'}
    assert likes['saved_to_video_memory'] is False
    folders=await shelf.read('folders');assert [r['folder_id'] for r in folders['folders']]==['1']
    with pytest.raises(CapabilityError):await shelf.read('favorites','2')
    assert backend.content_calls==[]
    content=await shelf.read('favorites','1')
    assert content['videos'][0]['author']=='UP' and 'fav_time' not in json.dumps(content)
    backend.content=AsyncMock(return_value={'info':{'id':1,'mid':'123','attr':1},'medias':[{'bvid':BV}]})
    with pytest.raises(CapabilityError):await shelf.read('favorites','1')

@pytest.mark.parametrize('text,expected',[('看看我公开点赞',True),('把收藏夹列出来',True),('不要看我的收藏',False),('我今天点赞了',False),('你好',False)])
def test_shelf_current_request_gate(text,expected):assert shelf_requested(text)==expected

async def test_shelf_tool_only_owner_private_and_explicit_request(plugin):
    plugin.config['bili_public_shelf_enabled']=True;plugin.bili_shelf.read=AsyncMock(return_value={'videos':[]})
    for e in [Event(private=False),Event(sender='other',admin=False)]:
        e.get_message_str=lambda:'看看我的点赞'
        assert json.loads(await plugin.bili_public_shelf(e))['ok'] is False
    e=Event();e.get_message_str=lambda:'别看我的收藏'
    assert json.loads(await plugin.bili_public_shelf(e))['ok'] is False
    plugin.bili_shelf.read.assert_not_awaited()
    e.get_message_str=lambda:'看看我的公开点赞'
    assert json.loads(await plugin.bili_public_shelf(e))['videos']==[]
    assert e.get_extra('fish_public_shelf_read')


async def test_scheduled_free_browse_uses_homepage_not_topic_search(tmp_path):
    from astrbot_plugin_fish_capabilities.services.bili_duty import BiliDuty
    from astrbot_plugin_fish_capabilities.services.bili_comments import BiliComments
    from test_bili_comments import Posting
    backend=Feed();reader=BiliReader(tmp_path/'b.db',backend,recommendation_enabled=True)
    config={'bili_recommendation_enabled':True,'bili_topics':['do not force search'],'bili_comment_enabled':False}
    async def generate(prompt):return '{"bvids":[]}'
    async def deliver(text):raise AssertionError('no unsolicited test send')
    result=await BiliDuty(reader,BiliComments(reader,config,Posting()),config,generate,deliver).once('test')
    assert result['state']=='abstained' and backend.calls==['recommended']


async def test_public_shelf_cannot_be_used_as_same_turn_recommendation_seed(plugin):
    plugin.config['bili_enabled']=True;e=Event();e.set_extra('fish_public_shelf_read',True)
    assert json.loads(await plugin.bili_browse(e,'从收藏提取的关键词'))['ok'] is False
    assert json.loads(await plugin.bili_scroll(e,'从点赞提取的关键词'))['ok'] is False
