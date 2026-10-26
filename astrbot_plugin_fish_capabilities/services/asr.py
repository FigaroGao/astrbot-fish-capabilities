"""Cloud ASR pool with scoped deduplication and conservative local reservations."""
import asyncio
import audioop
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit
import wave

from .policy import CapabilityError

MODELS={'paraformer-realtime-v2':16000,'paraformer-v2':16000,'paraformer-realtime-8k-v2':8000,'paraformer-8k-v2':8000}
HK=timezone(timedelta(hours=8))


class ASRRejected(Exception):
    def __init__(self,code):self.code=str(code)[:100];super().__init__('ASR request rejected')


class DashScopeASR:
    def __init__(self,key_reader):self.key_reader=key_reader

    def recognize(self,model,path):
        key=self.key_reader()
        if not key:raise CapabilityError('未找到向量模型引用的阿里云Key。')
        if model in ('paraformer-v2','paraformer-8k-v2'):return self.file_transcription(model,path,key)
        # Isolate the SDK's websocket threads from AstrBot's event loop. A hard
        # process timeout also stops its worker threads; cancelling to_thread
        # alone cannot do that. Credentials travel via stdin, never argv/logs.
        worker='''import json,sys,os
from dashscope.audio.asr import Recognition
p=json.load(sys.stdin)
try:
 r=Recognition(model=p['model'],callback=None,format='wav',sample_rate=p['rate'],api_key=p['key']).call(p['path'],timeout=25)
 out={'status':r.status_code,'code':str(r.code or ''),'text':''.join(str(s.get('text') or '') for s in (r.get_sentence() or [])) if r.status_code==200 else ''}
except Exception:
 out={'status':0,'code':'worker_failed','text':''}
print('ASR_RESULT:'+json.dumps(out,ensure_ascii=True),flush=True)
os._exit(0)
'''
        try:
            result=subprocess.run([sys.executable,'-c',worker],input=json.dumps(dict(model=model,rate=MODELS[model],key=key,path=str(path))),
                                  text=True,capture_output=True,timeout=40)
            line=next(line for line in reversed(result.stdout.splitlines()) if line.startswith('ASR_RESULT:'))
            response=json.loads(line[len('ASR_RESULT:'):])
        except Exception:raise CapabilityError('实时语音识别未完成，已停止识别子进程。') from None
        if response['status']!=200:raise ASRRejected(response['code'])
        return response['text']

    @staticmethod
    def official_url(value):
        u=urlsplit(value)
        if u.scheme!='https' or not (u.hostname or '').endswith('.aliyuncs.com') or u.username or u.password or u.port:
            raise CapabilityError('语音临时存储地址未通过校验。')
        return value

    def file_transcription(self,model,path,key):
        # Use the SDK for task submission and polling. Temporary storage expires
        # after 48 hours; never make the tablet's WebUI/audio directory public.
        import requests
        from dashscope.audio.asr import Transcription
        from dashscope.utils.oss_utils import OssUtils
        certificate=OssUtils.get_upload_certificate(model=model,api_key=key,timeout=20)
        if certificate.status_code!=200:raise ASRRejected(certificate.code)
        c=certificate.output
        object_key=c['upload_dir']+'/'+path.name
        form={k:c[k] for k in ('policy','x_oss_object_acl','x_oss_forbid_overwrite')}
        form={'policy':form['policy'],'x-oss-object-acl':form['x_oss_object_acl'],'x-oss-forbid-overwrite':form['x_oss_forbid_overwrite'],
              'OSSAccessKeyId':c['oss_access_key_id'],'Signature':c['signature'],'key':object_key,'success_action_status':'200'}
        with path.open('rb') as audio:
            result=requests.post(self.official_url(c['upload_host']),data=form,files={'file':(path.name,audio,'audio/wav')},timeout=(10,30),allow_redirects=False)
        if result.status_code!=200:raise CapabilityError('临时语音上传未完成。')
        response=Transcription.async_call(model=model,file_urls=['oss://'+object_key],api_key=key,
                    headers={'X-DashScope-OssResourceResolve':'enable'},timeout=25)
        if response.status_code!=200:raise ASRRejected(response.code)
        task=response.output.task_id
        deadline=time.monotonic()+70
        while time.monotonic()<deadline:
            response=Transcription.fetch(task,api_key=key,timeout=15)
            if response.status_code!=200:raise CapabilityError('转写任务查询未完成，不重复提交。')
            state=response.output.get('task_status')
            if state=='FAILED':raise CapabilityError('云端转写任务未成功，不重复提交。')
            if state=='SUCCEEDED':
                parts=[]
                for item in response.output.get('results',[])[:1]:
                    if item.get('subtask_status')!='SUCCEEDED':raise CapabilityError('云端转写子任务未成功。')
                    r=requests.get(self.official_url(item['transcription_url']),timeout=15,allow_redirects=False)
                    if r.status_code!=200 or len(r.content)>1_000_000:raise CapabilityError('转写结果暂不可用。')
                    for transcript in r.json().get('transcripts',[])[:1]:parts.append(str(transcript.get('text') or ''))
                return ''.join(parts)
            time.sleep(2)
        raise TimeoutError('ASR task still pending')


def normalize(source,target,rate,max_seconds):
    if not source.is_file() or source.is_symlink() or not 44<=source.stat().st_size<=20_000_000:
        raise CapabilityError('语音文件不存在或超过20MB。')
    try:
        with wave.open(str(source),'rb') as w:
            channels,width,sr,n=w.getnchannels(),w.getsampwidth(),w.getframerate(),w.getnframes()
            if channels not in (1,2) or width not in (1,2,3,4) or not 8000<=sr<=192000:
                raise CapabilityError('语音音频参数不支持。')
            duration=n/sr
            if not 0<duration<=max_seconds:raise CapabilityError('语音超过单条时长限制。')
            raw=w.readframes(n)
            if len(raw)!=n*width*channels:raise CapabilityError('语音文件不完整。')
        if width==1:raw=audioop.bias(raw,1,-128)
        if channels==2:raw=audioop.tomono(raw,width,.5,.5)
        if width!=2:raw=audioop.lin2lin(raw,width,2)
        if sr!=rate:raw=audioop.ratecv(raw,2,1,sr,rate,None)[0]
        with wave.open(str(target),'wb') as w:
            w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate);w.writeframes(raw)
        target.chmod(0o600)
        return duration
    except (wave.Error,EOFError) as exc:raise CapabilityError('需要有效PCM WAV；先使用AstrBot现有语音解码器。') from exc


class ASRPool:
    def __init__(self,path,backend,config,clock=time.time):
        self.path,self.backend,self.config,self.clock=path,backend,config,clock
        self.lock=asyncio.Lock()
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS asr_requests(scope TEXT,digest TEXT,model TEXT,month TEXT,stamp REAL,seconds INTEGER,state TEXT,text TEXT,PRIMARY KEY(scope,digest,model,month))')
        path.chmod(0o600)

    @contextmanager
    def db(self):
        db=sqlite3.connect(self.path,timeout=5)
        try:
            with db:yield db
        finally:db.close()

    def status(self):
        month=datetime.fromtimestamp(self.clock(),HK).strftime('%Y-%m')
        with self.db() as db:
            rows=db.execute('SELECT model,SUM(seconds) FROM asr_requests WHERE month=? GROUP BY model',(month,)).fetchall()
        return {'month':month,'reserved_seconds':dict(rows),'monthly_local_cap_per_model':int(self.config.get('asr_monthly_seconds',35000)),
                'is_cloud_quota':False,'instruction':'仅本平板保守预留量，不是阿里云真实剩余额度，也不证明不同模型免费量可以叠加。'}

    async def transcribe(self,source,scope):
        source=Path(source)
        if not source.is_file() or source.stat().st_size>20_000_000:raise CapabilityError('语音文件不可用或超过20MB。')
        digest=hashlib.sha256(source.read_bytes()).hexdigest()
        month=datetime.fromtimestamp(self.clock(),HK).strftime('%Y-%m')
        models=self.config.get('asr_models',['paraformer-realtime-v2','paraformer-v2','paraformer-realtime-8k-v2','paraformer-8k-v2'])
        if not isinstance(models,list) or not models or any(m not in MODELS for m in models):raise CapabilityError('语音识别模型池配置不正确。')
        async with self.lock:
            with self.db() as db:db.execute("UPDATE asr_requests SET text='' WHERE stamp<?",(self.clock()-86400,))
            for model in dict.fromkeys(models):
                with self.db() as db:
                    old=db.execute('SELECT state,text FROM asr_requests WHERE scope=? AND digest=? AND model=? AND month=?',(scope,digest,model,month)).fetchone()
                    if old:
                        if old[0]=='recognized' and old[1]:return {'text':old[1],'model':model,'cached':True}
                        if old[0]=='quota_denied':continue
                        raise CapabilityError('这段语音已尝试或结果不确定，不自动重复识别。')
                    if db.execute("SELECT 1 FROM asr_requests WHERE model=? AND month=? AND state='quota_denied'",(model,month)).fetchone():continue
                with tempfile.TemporaryDirectory(prefix='asr-',dir=self.path.parent) as td:
                    path=Path(td)/'voice.wav'
                    duration=normalize(source,path,MODELS[model],int(self.config.get('asr_max_seconds',180)))
                    seconds=math.ceil(duration)
                    with self.db() as db:
                        db.execute('BEGIN IMMEDIATE')
                        used=db.execute('SELECT COALESCE(SUM(seconds),0) FROM asr_requests WHERE model=? AND month=?',(model,month)).fetchone()[0]
                        if used+seconds>int(self.config.get('asr_monthly_seconds',35000)):continue
                        db.execute('INSERT INTO asr_requests VALUES(?,?,?,?,?,?,?,?)',(scope,digest,model,month,self.clock(),seconds,'reserved',''))
                    state,text='uncertain',''
                    try:
                        text=await asyncio.wait_for(asyncio.to_thread(self.backend.recognize,model,path),120)
                        if not isinstance(text,str) or len(text)>4000:raise CapabilityError('语音转写返回格式不正确。')
                        state='recognized' if text.strip() else 'no_speech'
                    except ASRRejected as exc:
                        if exc.code=='AllocationQuota.FreeTierOnly':state='quota_denied'
                        else:raise CapabilityError('语音模型未接受请求，请检查服务权限、地域或Key；未输出凭据。') from None
                    except asyncio.CancelledError:raise
                    except Exception:raise CapabilityError('语音识别未完成，已保留本地预留记录，不重复调用。') from None
                    finally:
                        with self.db() as db:db.execute('UPDATE asr_requests SET state=?,text=? WHERE scope=? AND digest=? AND model=? AND month=?',(state,text[:4000],scope,digest,model,month))
                    if state=='quota_denied':continue
                    return {'text':text.strip(),'model':model,'cached':False,'seconds':duration,'estimated_usage':True}
            raise CapabilityError('当前语音模型池的可用额度不足；没有切换到未配置的付费模型。')
