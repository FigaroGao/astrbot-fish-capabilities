"""Independent UTC+8 vision schedule; no global chat/provider mutation."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
from types import SimpleNamespace
import asyncio,base64,json,os,time,urllib.request
from .policy import CapabilityError
ZONE=timezone(timedelta(hours=8))
HOLIDAYS_2026=[('01-01','01-03'),('02-15','02-23'),('04-04','04-06'),('05-01','05-05'),('06-19','06-21'),('09-25','09-27'),('10-01','10-07')]

def peak(stamp=None,holidays=()):
    now=datetime.fromtimestamp(time.time() if stamp is None else stamp,ZONE)
    holiday=now.date().isoformat() in holidays or (now.year==2026 and any(a<=now.strftime('%m-%d')<=b for a,b in HOLIDAYS_2026))
    minute=now.hour*60+now.minute
    return now.weekday()<5 and not holiday and (540<=minute<720 or 840<=minute<1080)

def decision(config,root,stamp=None):
    if not config.get('vision_peak_routing_enabled',False):return 'existing'
    calendar=Path(root)/'vision-routing-calendar.private.json'
    holidays=json.loads(calendar.read_text(encoding='utf-8')).get('holidays',[]) if calendar.exists() else []
    if not isinstance(holidays,list):raise CapabilityError('识图日历格式无效。')
    return 'qwen3.8-omni-flash' if peak(stamp,holidays) else 'existing'

def _qwen(config,key_provider,prompt,system,images,tokens,timeout):
    from urllib.parse import urlsplit
    p=next((p for p in config.get('provider',[]) if p.get('id')==key_provider and p.get('enable',False)),None)
    if not p:raise CapabilityError('千问密钥来源未启用。')
    key=p.get('embedding_api_key','')
    if isinstance(key,list):key=next((k for k in key if k),'')
    if key.startswith('$'):key=os.environ.get(key[1:].strip('{}'),'')
    base=str(p.get('embedding_api_base','')).rstrip('/');url=urlsplit(base)
    if not key or url.scheme!='https' or not (url.hostname or '').endswith('.aliyuncs.com') or url.username or url.password:raise CapabilityError('需要阿里云官方区域接口和本机密钥。')
    if not 1<=len(images)<=24:raise CapabilityError('本次识图数量超出预算。')
    content=[{'type':'text','text':prompt}]
    for image in images:
        value=str(image)
        if not value.startswith(('data:image/','https://','http://')):
            f=Path(value);mime={'.png':'png','.jpg':'jpeg','.jpeg':'jpeg','.webp':'webp'}.get(f.suffix.lower())
            if not mime or not f.is_file() or f.stat().st_size>8*1024**2:raise CapabilityError('识图文件不可用或过大。')
            value='data:image/'+mime+';base64,'+base64.b64encode(f.read_bytes()).decode()
        if len(value)>12*1024**2:raise CapabilityError('识图输入过大。')
        content.append({'type':'image_url','image_url':{'url':value}})
    body={'model':'qwen3.8-omni-flash','messages':[{'role':'system','content':system},{'role':'user','content':content}],
          'max_tokens':tokens,'enable_thinking':False,'reasoning_effort':'none','enable_search':False,'temperature':0}
    request=urllib.request.Request(base+'/chat/completions',data=json.dumps(body,ensure_ascii=False).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args):raise CapabilityError('拒绝识图接口重定向。')
    with urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect()).open(request,timeout=timeout) as response:data=json.load(response)
    answer=data['choices'][0]['message'].get('content')
    if not isinstance(answer,str) or not answer.strip() or data['choices'][0].get('finish_reason')=='length':raise CapabilityError('千问识图输出未完成。')
    usage=data.get('usage',{});cached=usage.get('prompt_tokens_details',{}).get('cached_tokens',0)
    return SimpleNamespace(completion_text=answer,usage=SimpleNamespace(input_cached=cached,input_other=max(0,usage.get('prompt_tokens',0)-cached),output=usage.get('completion_tokens',0)))

async def qwen(config,key_provider,prompt,system,images,tokens,timeout):
    # Socket timeout bounds the thread. Never automatically replay a POST.
    return await asyncio.to_thread(_qwen,config,key_provider,prompt,system,images,tokens,timeout)
