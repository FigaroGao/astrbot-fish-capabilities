import json
import urllib.error
import pytest
from astrbot_plugin_fish_capabilities.services.http import PublicJSON,PublicRequestError
from astrbot_plugin_fish_capabilities.services.bilibili import BiliReader
from astrbot_plugin_fish_capabilities.services.policy import CapabilityError
from test_services import BV


def test_public_http_status_is_visible_without_sensitive_url(monkeypatch):
    class Opener:
        def open(self,*args,**kwargs):raise urllib.error.HTTPError('https://api.bilibili.com/path?secret=test',412,'private reason',{},None)
    monkeypatch.setattr('urllib.request.build_opener',lambda *args:Opener())
    with pytest.raises(PublicRequestError) as error:
        PublicJSON()._get('https://api.bilibili.com/path',{'api.bilibili.com'})
    assert error.value.http_status==412 and '412' in str(error.value)
    assert 'secret' not in str(error.value) and 'private reason' not in str(error.value)


async def test_repeated_rejected_read_stops_before_io_and_survives_restart(tmp_path,monkeypatch):
    now=[1000.];monkeypatch.setattr('time.time',lambda:now[0])
    class Backend:
        calls=0
        async def read(self,bv):
            self.calls+=1
            raise PublicRequestError(412)
    backend=Backend();path=tmp_path/'bili.db'
    with pytest.raises(PublicRequestError):await BiliReader(path,backend).read(BV,9)
    reader=BiliReader(path,backend)
    with pytest.raises(CapabilityError,match='5分钟'):await reader.read(BV,18)
    assert backend.calls==1
    with reader.connect() as db:assert db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0]==1
    now[0]+=301
    with pytest.raises(PublicRequestError):await reader.read(BV,6)
    assert backend.calls==2


async def test_optional_subtitle_http_failure_keeps_metadata_and_visual_route(monkeypatch):
    import sys,types
    from astrbot_plugin_fish_capabilities.services.bilibili import BiliBackend
    class Video:
        def __init__(self,**kwargs):pass
        async def get_subtitle(self,**kwargs):raise PublicRequestError(412)
        async def get_danmakus(self,**kwargs):return []
    monkeypatch.setitem(sys.modules,'bilibili_api',types.SimpleNamespace(video=types.SimpleNamespace(Video=Video)))
    backend=BiliBackend();backend.credential=lambda:None
    async def info(*args):return {'aid':1,'cid':2,'duration':20}
    backend.info=info
    result=await backend.read(BV)
    assert result['info']['cid']==2 and result['subtitle_status']=='unavailable_http_412'
    assert result['segments']==[]


async def test_bound_metadata_uses_normal_sdk_once_without_public_fallback(tmp_path,monkeypatch):
    import sys,types
    from unittest.mock import AsyncMock
    from astrbot_plugin_fish_capabilities.services.bilibili import BiliBackend
    path=tmp_path/'credentials.json';path.write_text('{}')
    get_info=AsyncMock(return_value={'bvid':BV,'duration':14,'cid':2})
    video=types.SimpleNamespace(Video=lambda **kw:types.SimpleNamespace(get_info=get_info))
    monkeypatch.setitem(sys.modules,'bilibili_api',types.SimpleNamespace(video=video))
    public=types.SimpleNamespace(get=AsyncMock())
    backend=BiliBackend(path,public);backend.credential=lambda:object()
    assert (await backend.info(BV))['duration']==14
    public.get.assert_not_called();get_info.assert_awaited_once()
    class Rejected(Exception):code=412
    get_info.side_effect=Rejected()
    with pytest.raises(PublicRequestError):await backend.info(BV)
    public.get.assert_not_called();assert get_info.await_count==2
