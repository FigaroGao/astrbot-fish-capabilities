"""Bounded 3x3 preview contact sheet; no full-video download."""
import asyncio,io,math,urllib.parse,urllib.request,hashlib
from pathlib import Path
from .http import PublicJSON,NoRedirect
from .policy import CapabilityError

def positions(index,duration,count=9):
    count=max(1,min(27,int(count)))
    valid=[(i,float(t)) for i,t in enumerate(index) if isinstance(t,(int,float)) and 0<=t<=duration]
    if not valid:return []
    chosen=[]
    for n in range(count):
        target=duration*(n+.5)/count
        item=min(valid,key=lambda r:abs(r[1]-target))
        if item not in chosen:chosen.append(item)
    return chosen

class Preview:
    def __init__(self,root):self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
    async def create(self,video_id,info,count=9):
        duration=float(info.get('duration',0))
        if not 0<duration<=600:raise CapabilityError('只读取不超过10分钟的视频。')
        result=await PublicJSON().get('https://api.bilibili.com/x/player/videoshot?'+urllib.parse.urlencode({'bvid':video_id,'cid':info.get('cid'),'index':1}),{'api.bilibili.com'})
        data=result.get('data') or {};chosen=positions(data.get('index',[]),duration,count)
        if result.get('code')!=0 or not chosen:raise CapabilityError('该视频没有可用预览图；没有下载整段视频。')
        return await asyncio.to_thread(self.build,video_id,data,chosen)
    def build(self,video_id,data,chosen):
        from PIL import Image,ImageDraw
        nx,ny,w,h=[int(data.get(k,0)) for k in ('img_x_len','img_y_len','img_x_size','img_y_size')]
        if not 1<=nx<=20 or not 1<=ny<=20 or not 16<=w<=640 or not 16<=h<=480:raise CapabilityError('预览图结构异常。')
        images=data.get('image',[]);loaded={};panels=[]
        for tile,stamp in chosen:
            page=tile//(nx*ny)
            if page>=len(images) or page>=3:continue
            if page not in loaded:
                url=str(images[page]);url='https:'+url if url.startswith('//') else url;p=urllib.parse.urlsplit(url)
                if p.scheme!='https' or not (p.hostname or '').endswith('.hdslb.com') or p.username or p.password or p.port not in (None,443):raise CapabilityError('预览图地址异常。')
                request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.bilibili.com/'})
                with urllib.request.build_opener(NoRedirect()).open(request,timeout=12) as response:raw=response.read(8_000_001)
                if len(raw)>8_000_000:raise CapabilityError('预览图过大。')
                image=Image.open(io.BytesIO(raw))
                if image.width*image.height>20_000_000:raise CapabilityError('预览图尺寸过大。')
                loaded[page]=image.convert('RGB')
            local=tile%(nx*ny);x=(local%nx)*w;y=(local//nx)*h
            if x+w>loaded[page].width or y+h>loaded[page].height:continue
            panels.append((loaded[page].crop((x,y,x+w,y+h)),stamp))
        if not panels:raise CapabilityError('没有可用预览画面。')
        paths=[];sheet_sizes=[]
        for offset in range(0,len(panels),9):
            batch=panels[offset:offset+9]
            columns=min(3,math.ceil(math.sqrt(len(batch))))
            rows=math.ceil(len(batch)/columns)
            canvas=Image.new('RGB',(columns*w,rows*(h+26)),'white');draw=ImageDraw.Draw(canvas)
            for i,(im,stamp) in enumerate(batch):
                x=(i%columns)*w;y=(i//columns)*(h+26)
                canvas.paste(im,(x,y))
                draw.text((x+4,y+h+2),str(offset+i+1)+' | '+str(int(stamp)//60)+':'+str(int(stamp)%60).zfill(2),fill='black')
            path=self.root/(hashlib.sha256((video_id+':native-v2:'+str(w)+':'+str(h)+':'+str(len(panels))+':'+str(offset)).encode()).hexdigest()[:20]+'.png')
            canvas.save(path);path.chmod(0o600);paths.append(path);sheet_sizes.append(list(canvas.size))
        return {'path':paths[0],'paths':paths,'timestamps':[t for _,t in panels],'frames':len(panels),
                'source_frame_size':[w,h],'sent_frame_size':[w,h],'sheet_sizes':sheet_sizes,
                'preview_layout_version':2,'method':'bilibili_preview_sprites','full_video_downloaded':False}
