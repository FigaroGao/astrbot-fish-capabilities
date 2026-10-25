import hashlib,json,sys,types
from pathlib import Path
from unittest.mock import AsyncMock
import pytest
from astrbot_plugin_fish_capabilities.services.valorant import ValorantRecords,private_save
from astrbot_plugin_fish_capabilities.services.bili_media import CommentMedia
from astrbot_plugin_fish_capabilities.services.memes import MemeLibrary
from astrbot_plugin_fish_capabilities.services.policy import CapabilityError
from test_valorant import Fake
from test_astrbot_binding import plugin,Event
from test_bili_comments import prepared,Posting


class Shop(Fake):
    async def post(self,path,data,auth=None):
        if path.endswith('/user_store'):
            self.calls.append((path,data,auth))
            return {'result':0,'data':{'end_ts':__import__('time').time()+3600,'list':[{'goods_name':'测试幻影','rmb_price':'129','token':'must-not-return','intent':'purchase'}]*4}}
        return await super().post(path,data,auth)


async def test_shop_read_only_whitelist_and_cache(tmp_path):
    p=tmp_path/'auth.json';private_save(p,{'login_type':'wechat','userId':'synthetic','tid':'secret'})
    http=Shop();r=ValorantRecords(p,http)
    value=await r.shop()
    assert len(value['items'])==4 and set(value['items'][0])=={'name','price_text'}
    assert 'must-not-return' not in json.dumps(value) and 'purchase' not in json.dumps(value)
    assert (await r.shop())['cached']
    assert len([c for c in http.calls if c[0].endswith('/user_store')])==1
    assert all(c[0] in ('/go/account/get_main_role_raw','/go/mlol_store/agame/user_store') for c in http.calls)


async def test_shop_login_failure_does_not_fabricate_items(tmp_path):
    p=tmp_path/'auth.json';private_save(p,{'login_type':'wechat','userId':'synthetic','tid':'secret'})
    http=Shop();r=ValorantRecords(p,http)
    http.post=AsyncMock(return_value={'result':1001})
    with pytest.raises(CapabilityError):await r.shop()


@pytest.mark.parametrize('has_daily',[True,False])
async def test_multi_section_shop_never_confuses_kingdom_with_daily(tmp_path,has_daily):
    p=tmp_path/'auth.json';private_save(p,{'login_type':'wechat','userId':'synthetic','tid':'secret'})
    class Sections(Shop):
        async def post(self,path,data,auth=None):
            if path.endswith('/user_store'):
                sections=[{'key':'kingdomstore','list':[{'goods_name':'王国商品'}]}]
                if has_daily:sections.append({'key':'dailystore','list':[{'goods_name':'每日商品'}]})
                return {'result':0,'data':sections}
            return await super().post(path,data,auth)
    reader=ValorantRecords(p,Sections())
    if has_daily:assert (await reader.shop())['items'][0]['name']=='每日商品'
    else:
        with pytest.raises(CapabilityError):await reader.shop()


async def test_shop_owner_private_only(plugin):
    plugin.config['valorant_shop_enabled']=True;plugin.valorant_records.shop=AsyncMock(return_value={'items':[]})
    for e in (Event(private=False),Event(sender='other'),Event(admin=False)):
        assert not json.loads(await plugin.valorant_shop(e))['ok']
    plugin.valorant_records.shop.assert_not_called()
    assert json.loads(await plugin.valorant_shop(Event()))=={'items':[]}


async def test_emote_catalog_uses_account_entitlements_and_does_not_buy(monkeypatch,tmp_path):
    credential=types.SimpleNamespace(dedeuserid='42')
    backend=types.SimpleNamespace(credential=lambda:credential)
    fetch=AsyncMock(return_value={'packages':[{'text':'小黄脸','emote':[{'text':'[doge]','flags':{'unlocked':False}},{'text':'[付费未买]','flags':{'unlocked':False}},{'text':'[自有表情]','flags':{'unlocked':True}}]}]})
    monkeypatch.setitem(sys.modules,'bilibili_api',types.SimpleNamespace(emoji=types.SimpleNamespace(get_emoji_list=fetch)))
    monkeypatch.setattr('astrbot_plugin_fish_capabilities.services.bili_media.CommentBackend.identity',AsyncMock(return_value='42'))
    m=CommentMedia(backend,MemeLibrary(tmp_path),{'bili_emote_enabled':True,'bili_account_id':'42'})
    assert await m.codes()==['[doge]','[自有表情]']
    await m.validate('哈哈[doge]')
    for text in ['[付费未买]','[doge][doge][doge]']:
        with pytest.raises(CapabilityError):await m.validate(text)
    assert fetch.await_count==1
    credential.dedeuserid='99'
    with pytest.raises(CapabilityError):await m.codes()


def library(tmp_path):
    from PIL import Image
    tmp_path.mkdir(exist_ok=True)
    image=tmp_path/'public.png';Image.new('RGB',(8,8),'blue').save(image)
    manifest=[dict(id='public',category='happy',file='public.png',sha256=hashlib.sha256(image.read_bytes()).hexdigest(),approved=True,visually_reviewed=True,source_repository='https://github.com/the-beating-light-of-the-nail/deepseek-chan-meme-pack',description='公开表情',image_text='哈哈')]
    (tmp_path/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
    return MemeLibrary(tmp_path),manifest


@pytest.mark.parametrize('case',['private_source','not_reviewed','changed_bytes','arbitrary_id'])
def test_private_or_unverified_images_cannot_be_uploaded(tmp_path,case):
    lib,rows=library(tmp_path)
    if case=='private_source':rows[0]['source_repository']='private album'
    if case=='not_reviewed':rows[0]['visually_reviewed']=False
    if case=='changed_bytes':(tmp_path/'public.png').write_bytes(b'changed')
    (tmp_path/'manifest.json').write_text(json.dumps(rows),encoding='utf-8')
    m=CommentMedia(None,lib,{'bili_comment_image_enabled':True})
    with pytest.raises(CapabilityError):m.image('../secret.png' if case=='arbitrary_id' else 'public')


async def test_image_and_text_review_precedes_any_upload(tmp_path):
    lib,rows=library(tmp_path/'memes')
    reader,p,w=await prepared(tmp_path)
    w.media=CommentMedia(None,lib,{'bili_comment_image_enabled':True})
    w.reviewer=types.SimpleNamespace(gate=AsyncMock(side_effect=CapabilityError('等待审核')))
    with pytest.raises(CapabilityError):await w.post(p['reading_id'],'哈哈',[p['evidence'][0]['evidence_id']],meme_id='public')
    assert w.backend.calls==0
    args=w.reviewer.gate.call_args.args
    assert args[1]['meme_sha256']==rows[0]['sha256'] and args[3]['_image_path'].endswith('public.png')


async def test_image_review_uses_vision_provider_without_path_in_prompt(plugin):
    plugin.config['bili_vision_provider_id']='vision-provider'
    plugin.bounded_generate=AsyncMock(return_value=types.SimpleNamespace(completion_text='{"decision":"allow"}'))
    await plugin.bili_public_review({'draft':'哈哈','public_material':{'_image_path':'/approved/meme.png','image_text':'哈哈'}})
    call=plugin.bounded_generate.call_args
    assert call.args[0]=='vision-provider' and call.kwargs['image_urls']==['/approved/meme.png']
    assert '_image_path' not in call.kwargs['prompt']


async def test_picture_is_passed_to_sdk_after_review_not_as_arbitrary_url(monkeypatch,tmp_path):
    from astrbot_plugin_fish_capabilities.services.bili_comments import CommentBackend
    image=types.SimpleNamespace(path=tmp_path/'verified.png')
    picture=object()
    factory=types.SimpleNamespace(from_file=lambda p:picture)
    send=AsyncMock(return_value={'rpid':123})
    comment=types.SimpleNamespace(send_comment=send,CommentResourceType=types.SimpleNamespace(VIDEO=1))
    monkeypatch.setitem(sys.modules,'bilibili_api',types.SimpleNamespace(comment=comment))
    monkeypatch.setitem(sys.modules,'bilibili_api.utils.picture',types.SimpleNamespace(Picture=factory))
    b=CommentBackend(types.SimpleNamespace(credential=lambda:'synthetic',info=AsyncMock(return_value={'aid':456})))
    await b.send('BV1xx411c7mD','哈哈',meme=image)
    assert send.call_args.kwargs['pic'] is picture and send.call_args.kwargs['text']=='哈哈'


async def test_image_digest_change_after_owner_approval_is_rejected(tmp_path):
    lib,rows=library(tmp_path/'memes');reader,p,w=await prepared(tmp_path)
    w.media=CommentMedia(None,lib,{'bili_comment_image_enabled':True})
    w.reviewer=types.SimpleNamespace(gate=AsyncMock())
    with pytest.raises(CapabilityError,match='改变'):
        await w.post(p['reading_id'],'哈哈',[p['evidence'][0]['evidence_id']],meme_id='public',meme_sha256='wrong')
    assert w.backend.calls==0;w.reviewer.gate.assert_not_called()


@pytest.mark.parametrize('query,term',[('KSKBL ZDJD','康神开播了'),('kskblzdjd','康神开播了'),('砌歪墙是什么意思','砌歪墙')])
def test_new_bili_meme_aliases_trigger_public_local_hints(tmp_path,query,term):
    from astrbot_plugin_fish_capabilities.services.knowledge import PublicKnowledge
    source=Path(__file__).resolve().parents[1]/'knowledge/vct-bili-20261025/entries.json'
    entries=json.loads(source.read_text(encoding='utf-8'))
    manifest=tmp_path/'entries.json';manifest.write_text(json.dumps(entries),encoding='utf-8')
    k=PublicKnowledge(None,{'knowledge_names':['game']},manifest)
    assert k.query_for(query)
    hints=k.local_meme_hints(query)
    assert any(term in x['title'] for x in hints)
    assert k.collections(k.query_for(query))==['game']
