import io,json,wave
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from astrbot_plugin_fish_capabilities.services.vocu import VocuBackend,payload,audio_url
from astrbot_plugin_fish_capabilities.services.policy import CapabilityError,Ledger
from astrbot_plugin_fish_capabilities.services.speech import Speech

VOICE='market:00000000-0000-0000-0000-000000000000'
def wav():
    b=io.BytesIO()
    with wave.open(b,'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(b'\0\0'*1600)
    return b.getvalue()

def test_settings_and_storage_boundary():
    p=payload({'voice_id':VOICE,'speed':0.9},'你好')
    assert p['voiceId']==VOICE and p['speechRate']==0.9 and p['vivid'] is False
    assert p['preset']=='balance' and 'api_key' not in p
    for bad in ['http://storage.vocu.ai/generate/x','https://evil.test/generate/x','https://storage.vocu.ai@evil.test/generate/x','https://storage.vocu.ai/private/x']:
        with pytest.raises(ValueError):audio_url(bad)
    with pytest.raises(ValueError):payload({'voice_id':VOICE,'speed':float('nan')},'x')

async def test_post_once_key_not_forwarded_and_pcm_conversion(tmp_path):
    key='test-key-never-output';cred=tmp_path/'key.json'
    cred.write_text(json.dumps(dict(api_key=key,voice_id=VOICE,speed=0.9)))
    requests=[]
    class Response(io.BytesIO):pass
    class Opener:
        def open(self,req,timeout):
            requests.append(req)
            if len(requests)==1:return Response(json.dumps({'status':200,'data':{'audio':'https://storage.vocu.ai/generate/fixture.mp3'}}).encode())
            return Response(b'ID3'+b'x'*100)
    def convert(cmd,**kwargs):
        from pathlib import Path
        Path(cmd[-1]).write_bytes(wav());return SimpleNamespace(returncode=0)
    with patch('urllib.request.build_opener',return_value=Opener()),patch('shutil.which',return_value='ffmpeg'),patch('subprocess.run',side_effect=convert):
        speech=Speech(tmp_path/'audio',Ledger(tmp_path/'ledger.db'),VocuBackend(cred))
        result=await speech.prepare('你好','vocu')
    assert result['path'].read_bytes()==wav()
    assert requests[0].get_method()=='POST' and requests[0].get_header('Authorization')=='Bearer '+key
    assert requests[1].get_header('Authorization') is None
    assert json.loads(requests[0].data)['speechRate']==0.9

async def test_uncertain_failure_no_retry_and_sanitized(tmp_path):
    cred=tmp_path/'key.json';cred.write_text(json.dumps(dict(api_key='private-secret-value',voice_id=VOICE,speed=0.9)))
    opener=SimpleNamespace(open=lambda *a,**kw:(_ for _ in ()).throw(RuntimeError('private-secret-value')))
    with patch('urllib.request.build_opener',return_value=opener),patch('shutil.which',return_value='ffmpeg'):
        with pytest.raises(CapabilityError) as exc:await VocuBackend(cred).synthesize('vocu','你好')
    assert 'private-secret-value' not in str(exc.value)
