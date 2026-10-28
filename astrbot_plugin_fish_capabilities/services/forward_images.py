"""Transient QQ forward images, bounded downloads and independent visual reading."""
import asyncio,io,json,socket,ipaddress,tempfile,urllib.parse,urllib.request
from pathlib import Path
from .http import NoRedirect

HOSTS={'multimedia.nt.qq.com','gchat.qpic.cn','c2cpicdw.qpic.cn','c2cpicdw.qpic.cn','gchat.qpic.cn','qpic.cn'}

def checked_url(url):
    p=urllib.parse.urlsplit(str(url))
    if p.scheme not in ('http','https') or p.hostname not in HOSTS or p.username or p.password or p.port not in (None,80,443):raise ValueError('unsupported_image_source')
    return urllib.parse.urlunsplit(('https',p.netloc.replace(':80',''),p.path,p.query,''))

def download(url,path):
    url=checked_url(url);host=urllib.parse.urlsplit(url).hostname
    if any(not ipaddress.ip_address(x[4][0]).is_global for x in socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)):raise ValueError('non_public_address')
    with urllib.request.build_opener(NoRedirect()).open(url,timeout=8) as r:data=r.read(6_000_001)
    if len(data)>6_000_000:raise ValueError('image_too_large')
    from PIL import Image
    with Image.open(io.BytesIO(data)) as image:
        if image.width*image.height>20_000_000:raise ValueError('image_too_large')
        image.seek(0);image.convert('RGB').save(path,'PNG')
    path.chmod(0o600)

async def describe(images,client,generate,root):
    results=[]
    with tempfile.TemporaryDirectory(prefix='forward-',dir=root) as directory:
        for row in images[:6]:
            label=row['label'];data=row['data'];path=Path(directory)/(label+'.png')
            try:
                url=data.get('url')
                if not url:
                    ticket=data.get('file')
                    if not isinstance(ticket,str) or not 1<=len(ticket)<=512:raise ValueError('missing_image')
                    value=await asyncio.wait_for(client.call('get_image',{'file':ticket}),5)
                    url=(value or {}).get('url')
                await asyncio.to_thread(download,url,path)
                text=await asyncio.wait_for(generate(path,label),25)
                if not isinstance(text,str) or not text.strip():raise ValueError('empty_description')
                results.append('['+label+' 图像读取结果，仅属对应转发节点] '+text[:1500])
            except asyncio.CancelledError:raise
            except Exception:results.append('['+label+' 图片读取失败或不可用，未识别图像；不能猜测内容]')
    return '\n'.join(results)
