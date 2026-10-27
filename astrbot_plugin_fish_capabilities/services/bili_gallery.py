"""Bounded real-video sampling for suspected slide/chat videos.

The entire declared timeline is sampled every 0.5s, not every source frame.
Brief flashes, scrolling and unreadable text remain explicitly uncertain.
No account cookies are sent to CDNs; signed stream URLs never enter logs.
"""
import asyncio
import shutil
import re
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

from .http import NoRedirect
from .policy import CapabilityError

MAX_BYTES=96*1024*1024
MAX_OUTPUT_BYTES=128*1024*1024
MAX_PAGES=48


def stream_url(value):
    p=urllib.parse.urlsplit(str(value))
    host=(p.hostname or '').lower()
    if p.scheme!='https' or not (host.endswith('.bilivideo.com') or host.endswith('.bilivideo.cn')) or p.username or p.password or p.port not in (None,443):
        raise CapabilityError('视频源不属于允许的B站媒体服务。')
    return str(value)


def media_user_agent():
    # Match the normal playback SDK's User-Agent rather than the truncated
    # Mozilla/5.0 string rejected by some Bilibili CDNs (HTTP 567).
    try:
        from bilibili_api.utils.network import HEADERS
        agent=str(HEADERS['User-Agent'])
    except (ImportError,KeyError):
        agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0'
    return agent


def download(url,path,stop):
    request=urllib.request.Request(stream_url(url),headers={'User-Agent':media_user_agent(),'Referer':'https://www.bilibili.com/','Range':'bytes=0-'})
    start=time.monotonic();total=0
    try:
        with urllib.request.build_opener(NoRedirect()).open(request,timeout=12) as response:
            status=getattr(response,'status',200)
            expected_size=None
            if status not in (200,206):raise CapabilityError('视频源未返回完整文件。')
            if status==206:
                match=re.fullmatch(r'bytes 0-(\d+)/(\d+)',response.headers.get('Content-Range',''))
                if not match or int(match[1])+1!=int(match[2]):raise CapabilityError('视频源只返回部分片段，未冒充完整下载。')
                expected_size=int(match[2])
                if int(match[2])>MAX_BYTES:raise CapabilityError('视频文件超过图片检查下载预算。')
            length=response.headers.get('Content-Length')
            if length and int(length)>MAX_BYTES:raise CapabilityError('视频文件超过图片检查下载预算。')
            with path.open('wb') as target:
                path.chmod(0o600)
                while True:
                    if stop.is_set() or time.monotonic()-start>60:raise CapabilityError('视频下载已停止或超时。')
                    chunk=response.read(64*1024)
                    if not chunk:break
                    total+=len(chunk)
                    if total>MAX_BYTES:raise CapabilityError('视频文件超过图片检查下载预算。')
                    target.write(chunk)
            if not total or (length and total!=int(length)) or (expected_size is not None and total!=expected_size):raise CapabilityError('视频文件不完整。')
        return total
    except CapabilityError:raise
    except Exception:raise CapabilityError('视频下载失败；没有记录播放凭据。') from None


def same_page(a,b):
    from PIL import ImageChops,ImageStat
    if a.size!=b.size:return False
    diff=ImageChops.difference(a,b)
    # Conservative compression tolerance. A high contrast new chat character
    # is retained even if it occupies a tiny fraction of the whole page.
    return max(v for _,v in diff.getextrema())<=8 and max(ImageStat.Stat(diff).mean)<=1.3


def collect(directory):
    from PIL import Image
    pages=[];files=sorted(Path(directory).glob('frame-*.jpg'));overflow=False
    for index,path in enumerate(files):
        with Image.open(path) as source:image=source.convert('RGB')
        match=next((p for p in pages if same_page(image,p['image'])),None)
        if match:
            match['last_seen']=index*.5
            continue
        if len(pages)>=MAX_PAGES:overflow=True;break
        pages.append({'id':f'g{index}','time':index*.5,'last_seen':index*.5,'image':image})
    return pages,{'source':'real_video_2fps','sample_interval_seconds':.5,'sampled_frames':len(files),
                  'unique_pages':len(pages),'page_limit_reached':overflow,
                  'scan_status':'page_limit_reached' if overflow else 'timeline_sampled',
                  'limitation':'每0.5秒取样，短暂闪图可能遗漏；页面判重有压缩容差，不证明源视频逐帧全读。'}


class GalleryScanner:
    def __init__(self,root,source,ffmpeg=None):
        self.root=Path(root);self.source=source;self.ffmpeg=ffmpeg or shutil.which('ffmpeg')
        self.lock=asyncio.Lock()

    async def scan(self,video_id,info):
        if not self.ffmpeg:return [],{'scan_status':'ffmpeg_unavailable','source':'preview_only'}
        duration=float(info.get('duration',0))
        if not 0<duration<=600:raise CapabilityError('图片检查只接受不超过10分钟的视频。')
        async with self.lock:
            self.root.mkdir(parents=True,exist_ok=True);self.root.chmod(0o700)
            with tempfile.TemporaryDirectory(dir=self.root,prefix='gallery-') as folder:
                directory=Path(folder);path=directory/'source.mp4';stop=threading.Event()
                url=await asyncio.wait_for(self.source(video_id,info),15)
                task=asyncio.create_task(asyncio.to_thread(download,url,path,stop))
                try:downloaded=await asyncio.shield(task)
                except asyncio.CancelledError:
                    stop.set()
                    try:await task
                    except Exception:pass
                    raise
                process=await asyncio.create_subprocess_exec(self.ffmpeg,'-nostdin','-hide_banner','-v','error',
                    '-protocol_whitelist','file,pipe','-threads','1','-i',str(path),'-an','-sn','-dn','-t',str(duration),
                    '-vf',r'fps=2,scale=w=min(1280\,iw):h=min(1280\,ih):force_original_aspect_ratio=decrease',
                    '-threads','1','-q:v','3','-frames:v','1201',str(directory/'frame-%06d.jpg'),
                    stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL)
                async def watch():
                    deadline=time.monotonic()+90
                    while process.returncode is None:
                        if time.monotonic()>deadline or sum(p.stat().st_size for p in directory.glob('frame-*.jpg'))>MAX_OUTPUT_BYTES:
                            raise CapabilityError('图片检查解码超过时间或磁盘预算。')
                        await asyncio.sleep(.25)
                watcher=asyncio.create_task(watch())
                waiter=asyncio.create_task(process.wait())
                try:
                    done,_=await asyncio.wait([watcher,waiter],return_when=asyncio.FIRST_COMPLETED)
                    if watcher in done:await watcher
                    if await waiter:raise CapabilityError('本地视频解码失败。')
                finally:
                    if process.returncode is None:
                        try:process.kill()
                        except ProcessLookupError:pass
                        await process.wait()
                    watcher.cancel();waiter.cancel()
                    await asyncio.gather(watcher,waiter,return_exceptions=True)
                collection=asyncio.create_task(asyncio.to_thread(collect,directory))
                try:pages,status=await asyncio.shield(collection)
                except asyncio.CancelledError:
                    # Do not remove the temporary directory under a live reader.
                    await collection
                    raise
                if not pages:raise CapabilityError('没有提取到视频画面。')
                status['download_bytes']=downloaded
                status['timeline_end_sampled']=max(0,status['sampled_frames']-1)*.5
                status['declared_duration']=duration
                status['timeline_tail_gap']=max(0,duration-status['timeline_end_sampled'])
                if status['timeline_tail_gap']>1:status['scan_status']='incomplete_timeline'
                return pages,status
