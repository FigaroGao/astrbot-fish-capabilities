from __future__ import annotations

import asyncio
import re
import secrets
import io
import wave
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .policy import CapabilityError, Ledger


SAMBERT_MODELS={
    'sambert-zhide-v1':{'name':'知德','style':'新闻男声','language':'中文＋英文'},
    'sambert-zhida-v1':{'name':'知达','style':'标准男声','language':'中文＋英文'},
    'sambert-zhishu-v1':{'name':'知树','style':'资讯男声','language':'中文＋英文'},
    'sambert-zhiyue-v1':{'name':'知悦','style':'温柔女声','language':'中文＋英文'},
    'sambert-eva-v1':{'name':'Eva','style':'陪伴女声','language':'美式英文'},
    'sambert-beth-v1':{'name':'Beth','style':'咨询女声','language':'美式英文'},
}


def plain_speech(text: str, *, max_chars: int = 180) -> str:
    if not isinstance(text,str): raise CapabilityError('语音内容必须是文字。')
    text=re.sub('<[^>]*>','',text)
    text=re.sub(r'https?://\S+','链接已保留在文字消息中',text)
    text=re.sub(r'[`*_#]','',text).strip()
    if not text or len(text)>max_chars:
        raise CapabilityError(f'单条语音请控制在 1～{max_chars} 字，长回答保持文字。')
    return text


class SambertBackend:
    def __init__(self, api_key: str): self.key=api_key

    async def synthesize(self, model: str, text: str) -> bytes:
        def run():
            from dashscope.audio.tts import SpeechSynthesizer
            response=SpeechSynthesizer.call(model=model,text=text,format='wav',sample_rate=16000,api_key=self.key)
            audio=response.get_audio_data()
            if not audio: raise CapabilityError('合成没有返回音频，请核对模型服务开通状态。')
            return audio
        try: return await asyncio.wait_for(asyncio.to_thread(run),35)
        except CapabilityError: raise
        except Exception as exc: raise CapabilityError('Sambert 合成失败；没有把服务返回值或密钥写入日志。') from exc


class Speech:
    def __init__(self, directory: Path, ledger: Ledger, backend=None, *, monthly_chars: int = 3000,
                 max_chars: int = 180):
        self.directory=directory; self.ledger=ledger; self.backend=backend
        self.monthly_chars=monthly_chars; self.max_chars=max_chars
        self.lock=asyncio.Lock()

    async def prepare(self, text: str, model: str) -> dict:
        text=plain_speech(text,max_chars=self.max_chars)
        if model not in SAMBERT_MODELS:
            raise CapabilityError('这个适配器仅支持已核对的 Sambert 模型；ASR 不能合成语音，Qwen 3.1 另走已验证的供应商适配。')
        if self.backend is None: raise CapabilityError('尚未配置语音凭据或适配器。')
        # This is a local cap, not an authoritative balance query for the account.
        month=datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m')
        async with self.lock:
            self.ledger.charge_tts(model,len(text),month,self.monthly_chars)
            # Keep the reservation on uncertain network failures: the remote call may
            # already have been billed. Only a verified balance can reconcile it.
            audio=await self.backend.synthesize(model,text)
            if not isinstance(audio,bytes) or not 44<=len(audio)<=4_000_000 or audio[:4]!=b'RIFF' or audio[8:12]!=b'WAVE':
                raise CapabilityError('合成音频不是有效大小的 WAV，未加入消息。')
            try:
                with wave.open(io.BytesIO(audio),'rb') as wav:
                    if wav.getnchannels() not in (1,2) or wav.getsampwidth()!=2 or wav.getframerate()!=16000 or wav.getnframes()<=0:
                        raise CapabilityError('WAV 参数不符合 16kHz PCM 输出要求。')
                    if len(wav.readframes(wav.getnframes()))!=wav.getnframes()*wav.getnchannels()*wav.getsampwidth():
                        raise CapabilityError('合成 WAV 数据不完整。')
            except (wave.Error,EOFError) as exc:
                raise CapabilityError('合成 WAV 无法解析。') from exc
            self.directory.mkdir(parents=True,exist_ok=True)
            output=self.directory/('speech-'+secrets.token_hex(8)+'.wav')
            output.write_bytes(audio);output.chmod(0o600)
            return {'path':output,'text':text,'model':model,'estimated_input_characters':len(text),
                    'quota_is_local_estimate':True}

    def cleanup(self, keep_seconds: int = 3600) -> int:
        import time
        removed=0
        if self.directory.is_dir():
            for file in self.directory.glob('speech-*.wav'):
                if file.is_file() and not file.is_symlink() and time.time()-file.stat().st_mtime>keep_seconds:
                    file.unlink();removed+=1
        return removed
