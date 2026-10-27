import json
import os
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from astrbot_plugin_fish_capabilities.services.bili_gallery import GalleryScanner,collect,same_page,stream_url
from astrbot_plugin_fish_capabilities.services.bili_storyboard import Storyboard
from astrbot_plugin_fish_capabilities.services.policy import CapabilityError


def frame(i):
    return {'id':f'f{i}','time':i*.5,'image':Image.new('RGB',(80,80),(i*9%256,20,30))}


def test_stream_domains_and_new_chat_text():
    assert stream_url('https://upos-a.bilivideo.com/video.mp4').startswith('https:')
    for url in ['http://a.bilivideo.com/a','https://evil.com/a','https://bilivideo.com.evil.com/a','https://u:p@a.bilivideo.com/a','https://a.bilivideo.com:123/a']:
        with pytest.raises(CapabilityError):stream_url(url)
    a=Image.new('RGB',(80,80),'white');b=a.copy()
    assert same_page(a,b)
    b.putpixel((50,50),(0,0,0))
    assert not same_page(a,b)


def test_download_player_headers_and_full_range_validation(tmp_path,monkeypatch):
    import threading,urllib.request
    from astrbot_plugin_fish_capabilities.services.bili_gallery import download
    class Response:
        status=206
        headers={'Content-Length':'4','Content-Range':'bytes 0-3/4'}
        def __enter__(self):self.sent=False;return self
        def __exit__(self,*args):pass
        def read(self,n):
            if self.sent:return b''
            self.sent=True;return b'data'
    response=Response();requests=[]
    class Opener:
        def open(self,request,**kwargs):requests.append(request);return response
    monkeypatch.setattr(urllib.request,'build_opener',lambda *args:Opener())
    assert download('https://a.bilivideo.com/a',tmp_path/'video',threading.Event())==4
    assert requests[0].get_header('Range')=='bytes=0-'
    assert len(requests[0].get_header('User-agent'))>30
    assert requests[0].get_header('Cookie') is None
    response.headers={'Content-Length':'4','Content-Range':'bytes 0-3/100'}
    with pytest.raises(CapabilityError):download('https://a.bilivideo.com/a',tmp_path/'partial',threading.Event())


async def test_gallery_reads_every_page_even_requested_one(tmp_path):
    frames=[frame(i) for i in range(13)];seen=[]
    async def candidates(*args):return frames
    async def generate(prompt,paths,kind,tokens):
        if kind=='bili_visual_plan':return json.dumps({'type':'slides','ads':[]})
        manifest=json.loads(prompt.split('实际图片：')[-1]);seen.extend(p['id'] for p in manifest)
        return json.dumps({'pages':[{'id':p['id'],'status':'read','text':'本页实际内容'} for p in manifest]})
    result=await Storyboard(SimpleNamespace(root=tmp_path,candidates=candidates),generate).read({'bvid':'BVtest','preview_requested':1},{})
    assert seen==[f'f{i}' for i in range(13)]
    assert len(result['gallery_pages'])==13 and result['gallery_all_available_pages_read']


async def test_missing_unreadable_and_ad_pages_not_called_complete(tmp_path):
    frames=[frame(i) for i in range(4)]
    async def candidates(*args):return frames
    async def generate(prompt,paths,kind,tokens):
        if kind=='bili_visual_plan':return json.dumps({'type':'chat'})
        return json.dumps({'pages':[{'id':'f0','status':'read','text':'正文'},
                                   {'id':'f1','status':'unreadable'},
                                   {'id':'f2','status':'advertisement','text':'不传播这段广告','explicit_promotion':True,'confidence':.95,'reason':'可见明确下载下单引导'}]})
    result=await Storyboard(SimpleNamespace(root=tmp_path,candidates=candidates),generate).read({'bvid':'BVtest'}, {})
    assert result['gallery_unread_page_ids']==['f1','f3']
    assert not result['gallery_all_available_pages_read']
    assert result['gallery_excluded_ad_pages'][0]['id']=='f2'
    assert '不传播这段广告' not in result['visual_summary']


async def test_visible_character_with_unreadable_subtitle_keeps_partial_evidence(tmp_path):
    frames=[frame(0)]
    async def generate(prompt,paths,kind,tokens):
        return json.dumps({'pages':[{'id':'f0','status':'partial','text':'可确认白色龙角和龙尾，底部小字无法辨认。'}]})
    result=await Storyboard(SimpleNamespace(root=tmp_path),generate).read_pages(frames,[],'ok',{'source':'preview_only'})
    assert result['visual_content_seen'] and result['gallery_pages'][0]['partial']
    assert result['gallery_partial_page_ids']==['f0'] and not result['gallery_all_available_pages_read']


async def test_scan_failure_still_reads_available_previews(tmp_path):
    frames=[frame(i) for i in range(2)]
    async def candidates(*args):return frames
    async def scan(*args):raise RuntimeError('do not expose signed URL')
    async def generate(prompt,paths,kind,tokens):
        if kind=='bili_visual_plan':return json.dumps({'type':'slides'})
        return json.dumps({'pages':[{'id':p['id'],'status':'read','text':'可见内容'} for p in frames]})
    result=await Storyboard(SimpleNamespace(root=tmp_path,candidates=candidates),generate,SimpleNamespace(scan=scan)).read({'bvid':'BVtest'}, {})
    assert result['gallery_scan']['scan_status']=='unavailable'
    assert not result['gallery_all_video_pages_confirmed']
    assert 'signed URL' not in str(result)


async def test_playback_uses_provided_safe_backup_without_arbitrary_rewrite(monkeypatch):
    import sys,types
    from astrbot_plugin_fish_capabilities.services.bilibili import BiliBackend
    class Video:
        def __init__(self,**kwargs):pass
        async def get_download_url(self,**kwargs):
            return {'dash':{'video':[{'codecs':'avc1.64001f','height':720,'width':1280,'bandwidth':200000,
                    'baseUrl':'http://not-permitted.bilivideo.com/video','backupUrl':['https://safe.bilivideo.com/video']}]}}
    fake=types.ModuleType('bilibili_api');fake.video=SimpleNamespace(Video=Video)
    monkeypatch.setitem(sys.modules,'bilibili_api',fake)
    backend=BiliBackend();backend.credential=lambda:None
    assert await backend.gallery_stream('BV1jg866XEC8',{'cid':1})=='https://safe.bilivideo.com/video'


async def test_real_ffmpeg_scan_three_images_without_network(tmp_path,monkeypatch):
    ffmpeg=os.environ.get('FISH_TEST_FFMPEG') or shutil.which('ffmpeg')
    if not ffmpeg:pytest.skip('ffmpeg not available; integration not claimed')
    source=tmp_path/'fixture.mp4'
    # Synthetic solid-color pages only; no QQ data, no third-party footage.
    cmd=[ffmpeg,'-hide_banner','-loglevel','error','-f','lavfi','-i','color=red:s=320x240:r=10:d=2',
         '-f','lavfi','-i','color=blue:s=320x240:r=10:d=2','-f','lavfi','-i','color=green:s=320x240:r=10:d=2',
         '-filter_complex','[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]','-map','[v]','-c:v','libx264','-pix_fmt','yuv420p',str(source)]
    subprocess.run(cmd,check=True,capture_output=True,timeout=20)
    import astrbot_plugin_fish_capabilities.services.bili_gallery as module
    def fake_download(url,path,stop):shutil.copyfile(source,path);return source.stat().st_size
    monkeypatch.setattr(module,'download',fake_download)
    async def get_source(*args):return 'https://test.bilivideo.com/synthetic.mp4'
    scanner=GalleryScanner(tmp_path/'scan',get_source,ffmpeg)
    pages,status=await scanner.scan('BVtest',{'duration':6})
    assert len(pages)==3 and status['sampled_frames']==12
    assert status['scan_status']=='timeline_sampled' and status['timeline_tail_gap']<=.5
    assert list((tmp_path/'scan').iterdir())==[]
