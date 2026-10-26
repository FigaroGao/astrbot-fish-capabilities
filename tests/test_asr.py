import asyncio
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
import wave
import pytest
from test_astrbot_binding import plugin,Event
from astrbot_plugin_fish_capabilities.services.asr import ASRPool,ASRRejected,normalize,DashScopeASR
from astrbot_plugin_fish_capabilities.services.policy import CapabilityError


def audio(path,duration=1,rate=24000):
    with wave.open(str(path),'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate);w.writeframes(b'\x00\x00'*int(rate*duration))
    return path

class Backend:
    def __init__(self):self.calls=[];self.fail={}
    def recognize(self,model,path):
        self.calls.append(model)
        with wave.open(str(path)) as w:assert w.getnchannels()==1 and w.getsampwidth()==2 and w.getframerate() in (8000,16000)
        if model in self.fail:raise self.fail[model]
        return '我去上课了'


def pool(tmp_path,**config):
    backend=Backend();cfg={'asr_models':['paraformer-realtime-v2','paraformer-realtime-8k-v2'],'asr_monthly_seconds':10,'asr_max_seconds':180};cfg.update(config)
    return ASRPool(tmp_path/'asr.db',backend,cfg),backend

async def test_audio_cached_only_within_same_scope(tmp_path):
    p,b=pool(tmp_path);f=audio(tmp_path/'a.wav')
    assert (await p.transcribe(f,'private'))['text']=='我去上课了'
    assert (await p.transcribe(f,'private'))['cached']
    assert not (await p.transcribe(f,'group'))['cached']
    assert len(b.calls)==2

async def test_local_exhaustion_selects_next_pool_model(tmp_path):
    p,b=pool(tmp_path,asr_monthly_seconds=1);f=audio(tmp_path/'a.wav')
    await p.transcribe(f,'one');await p.transcribe(f,'two')
    assert b.calls==['paraformer-realtime-v2','paraformer-realtime-8k-v2']
    with pytest.raises(CapabilityError):await p.transcribe(f,'three')
    assert len(b.calls)==2 and p.status()['is_cloud_quota'] is False

async def test_only_definite_free_quota_rejection_allows_fallback(tmp_path):
    p,b=pool(tmp_path);b.fail['paraformer-realtime-v2']=ASRRejected('AllocationQuota.FreeTierOnly');f=audio(tmp_path/'a.wav')
    assert (await p.transcribe(f,'one'))['model']=='paraformer-realtime-8k-v2'
    await p.transcribe(f,'two')
    assert b.calls==['paraformer-realtime-v2','paraformer-realtime-8k-v2','paraformer-realtime-8k-v2']

@pytest.mark.parametrize('error',[TimeoutError('secret!'),ASRRejected('InvalidApiKey'),RuntimeError('secret!')])
async def test_uncertain_or_auth_failure_never_retries_across_models(tmp_path,error):
    p,b=pool(tmp_path);b.fail['paraformer-realtime-v2']=error;f=audio(tmp_path/'a.wav')
    for _ in range(2):
        with pytest.raises(CapabilityError) as exc:await p.transcribe(f,'one')
        assert 'secret!' not in str(exc.value)
    assert len(b.calls)==1

async def test_no_speech_is_not_retried(tmp_path):
    p,b=pool(tmp_path);b.recognize=lambda *args:'';f=audio(tmp_path/'a.wav')
    assert (await p.transcribe(f,'one'))['text']==''
    with pytest.raises(CapabilityError):await p.transcribe(f,'one')

async def test_duration_validation_before_cloud_reservation(tmp_path):
    p,b=pool(tmp_path,asr_max_seconds=1);f=audio(tmp_path/'a.wav',2)
    with pytest.raises(CapabilityError):await p.transcribe(f,'one')
    assert b.calls==[] and p.status()['reserved_seconds']=={}

async def test_month_resets_local_cap_but_not_cloud_claim(tmp_path):
    p,b=pool(tmp_path,asr_monthly_seconds=1,asr_models=['paraformer-realtime-v2']);f=audio(tmp_path/'a.wav')
    clock=[datetime(2026,10,31,1,tzinfo=timezone.utc).timestamp()];p.clock=lambda:clock[0]
    await p.transcribe(f,'one')
    clock[0]+=2*86400
    await p.transcribe(f,'two');assert len(b.calls)==2

async def test_expired_cached_text_does_not_resubmit(tmp_path):
    p,b=pool(tmp_path);clock=[1000];p.clock=lambda:clock[0];f=audio(tmp_path/'a.wav')
    await p.transcribe(f,'one');clock[0]+=90000
    with pytest.raises(CapabilityError):await p.transcribe(f,'one')
    with p.db() as db:assert db.execute('SELECT text FROM asr_requests').fetchone()[0]==''
    assert len(b.calls)==1

@pytest.mark.parametrize('url',['http://a.aliyuncs.com/file','https://evil.example/file','https://u:p@oss.aliyuncs.com/file','https://oss.aliyuncs.com:443/file'])
def test_temporary_upload_never_targets_arbitrary_hosts(url):
    with pytest.raises(CapabilityError):DashScopeASR.official_url(url)

async def test_voice_becomes_current_sender_text_and_preserves_group_mute(plugin,monkeypatch,tmp_path):
    module=__import__(plugin.__class__.__module__,fromlist=['Comp'])
    class Plain:
        def __init__(self,text):self.text=text
    class Record:
        async def convert_to_file_path(self):return 'audio.wav'
    monkeypatch.setattr(module.Comp,'Plain',Plain,raising=False);monkeypatch.setattr(module.Comp,'Record',Record)
    plugin.config.update(asr_enabled=True,command_platform_ids=['qq_test'])
    plugin.asr.transcribe=AsyncMock(return_value={'text':'我去上课了','model':'paraformer-realtime-v2'})
    e=Event();e.message_str='';e.message_obj=NS(message_str='');e.get_message_str=lambda:e.message_str;e.unified_msg_origin='qq_test:FriendMessage:10001';parts=[Record()];e.get_messages=lambda:parts
    await plugin.recognize_voice(e)
    assert '我去上课了' in e.message_str and isinstance(parts[0],Plain)
    await plugin.recognize_voice(e);assert plugin.asr.transcribe.await_count==1
    g=Event(private=False);g.unified_msg_origin='qq_test:GroupMessage:77777';g.get_messages=lambda:[Record()]
    plugin.group_quiet.set(g.unified_msg_origin,120)
    await plugin.recognize_voice(g);assert plugin.asr.transcribe.await_count==1

async def test_unapproved_private_voice_never_uploaded(plugin,monkeypatch):
    plugin.config.update(asr_enabled=True,command_platform_ids=['qq_test'])
    plugin.asr.transcribe=AsyncMock()
    await plugin.recognize_voice(Event(sender='stranger',admin=False))
    assert not plugin.asr.transcribe.called


async def test_default_pool_only_uses_user_listed_monthly_models(tmp_path):
    b=Backend();p=ASRPool(tmp_path/'defaults.db',b,{})
    result=await p.transcribe(audio(tmp_path/'a.wav'),'private')
    assert result['model']=='paraformer-realtime-v2'


def test_realtime_worker_key_uses_stdin_and_has_hard_timeout(monkeypatch,tmp_path):
    from astrbot_plugin_fish_capabilities.services import asr
    def run(argv,**kwargs):
        assert 'test-secret' not in str(argv)
        assert kwargs['timeout']==40
        assert __import__('json').loads(kwargs['input'])['key']=='test-secret'
        return NS(stdout='ASR_RESULT:{"status":200,"code":"","text":"你好"}\n',returncode=0)
    monkeypatch.setattr(asr.subprocess,'run',run)
    assert DashScopeASR(lambda:'test-secret').recognize('paraformer-realtime-8k-v2',tmp_path/'a.wav')=='你好'


def test_realtime_worker_failure_never_returns_raw_stderr_or_key(monkeypatch,tmp_path):
    from astrbot_plugin_fish_capabilities.services import asr
    def run(*args,**kwargs):raise TimeoutError('test-secret')
    monkeypatch.setattr(asr.subprocess,'run',run)
    with pytest.raises(CapabilityError) as exc:DashScopeASR(lambda:'test-secret').recognize('paraformer-realtime-8k-v2',tmp_path/'a.wav')
    assert 'test-secret' not in str(exc.value)


async def test_four_authorized_monthly_models_are_all_reachable_by_budget(tmp_path):
    models=['paraformer-realtime-v2','paraformer-v2','paraformer-realtime-8k-v2','paraformer-8k-v2']
    p,b=pool(tmp_path,asr_monthly_seconds=1,asr_models=models)
    f=audio(tmp_path/'sample.wav')
    for i,model in enumerate(models):assert (await p.transcribe(f,str(i)))['model']==model
    with pytest.raises(CapabilityError):await p.transcribe(f,'fifth')
    assert b.calls==models


def test_8k_recorded_model_uses_file_endpoint(monkeypatch,tmp_path):
    backend=DashScopeASR(lambda:'fake-key')
    seen=[]
    def file(model,path,key):seen.append((model,key));return '识别成功'
    monkeypatch.setattr(backend,'file_transcription',file)
    assert backend.recognize('paraformer-8k-v2',tmp_path/'sample.wav')=='识别成功'
    assert seen==[('paraformer-8k-v2','fake-key')]
