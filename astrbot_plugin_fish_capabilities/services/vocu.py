"""Vocu short TTS. Credentials stay local; URLs, headers and errors are never logged."""
import asyncio,json,shutil,subprocess,tempfile,urllib.request,urllib.parse
from pathlib import Path
from .policy import CapabilityError

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args):raise ValueError('redirect_refused')

def payload(settings,text):
    import re,math
    voice=settings.get('voice_id','');speed=settings.get('speed',0.9)
    if not isinstance(voice,str) or not re.fullmatch(r'(?:market:)?[a-fA-F0-9-]{36}',voice):raise ValueError('voice_id')
    if type(speed) not in (float,int) or not math.isfinite(speed) or not 0.5<=speed<=2:raise ValueError('speed')
    return dict(voiceId=voice,text=text,promptId='default',preset='balance',speechRate=speed,
                vivid=False,flash=False,stream=False,srt=False,seed=-1)

def audio_url(url):
    p=urllib.parse.urlsplit(url)
    if p.scheme!='https' or p.hostname not in ('storage.vocu.ai','storage.vocustatic.com') or p.username or p.password or p.port not in (None,443) or not p.path.startswith('/generate/'):
        raise ValueError('audio_host')
    return url

class VocuBackend:
    def __init__(self,credentials):self.credentials=Path(credentials)

    def _run(self,text):
        settings=json.loads(self.credentials.read_text(encoding='utf-8'))
        key=settings.get('api_key','')
        if not isinstance(key,str) or not 10<=len(key)<=2048 or any(c.isspace() for c in key):raise ValueError('key')
        native=Path('/data/data/com.termux/files/usr/bin/ffmpeg')
        ffmpeg=shutil.which('ffmpeg') or (str(native) if native.is_file() else None)
        if not ffmpeg:raise ValueError('ffmpeg_missing')
        opener=urllib.request.build_opener(NoRedirect())
        req=urllib.request.Request('https://v1.vocu.ai/api/tts/simple-generate',data=json.dumps(payload(settings,text),ensure_ascii=False).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
        # Deliberately bounded; an uncertain timeout is never automatically retried.
        with opener.open(req,timeout=45) as res:raw=res.read(262145)
        if len(raw)>262144:raise ValueError('response_large')
        data=json.loads(raw)
        if data.get('status')!=200:raise ValueError('synthesis_failed')
        url=audio_url(data['data']['audio'])
        # Storage request receives no API credential header.
        with opener.open(urllib.request.Request(url),timeout=20) as res:mp3=res.read(4_000_001)
        if not 44<=len(mp3)<=4_000_000:raise ValueError('audio_size')
        with tempfile.TemporaryDirectory(prefix='fish-vocu-') as temp:
            inp=Path(temp)/'in.mp3';out=Path(temp)/'out.wav';inp.write_bytes(mp3)
            result=subprocess.run([ffmpeg,'-nostdin','-hide_banner','-loglevel','error','-i',str(inp),'-t','91','-ac','1','-ar','16000','-c:a','pcm_s16le',str(out)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=20)
            if result.returncode or not out.is_file():raise ValueError('conversion_failed')
            wav=out.read_bytes()
            if not 44<=len(wav)<=2_880_100:raise ValueError('duration_or_size')
            return wav

    async def synthesize(self,model,text):
        if model!='vocu':raise CapabilityError('Vocu适配器不能调用其他供应商模型。')
        try:return await asyncio.to_thread(self._run,text)
        except Exception:raise CapabilityError('Vocu语音未完成，请检查本机凭据、音色权限、余额、网络或ffmpeg；结果不确定时不自动重试，未输出密钥或服务原文。') from None
