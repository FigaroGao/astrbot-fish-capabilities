import asyncio
import hashlib
import json
import sqlite3
import time
import io
import wave
from pathlib import Path

import pytest

from astrbot_plugin_fish_capabilities.services.bilibili import BiliReader, bvid
from astrbot_plugin_fish_capabilities.services.device import DeviceBridge
from astrbot_plugin_fish_capabilities.services.history import GroupHistory
from astrbot_plugin_fish_capabilities.services.http import PublicJSON
from astrbot_plugin_fish_capabilities.services.intent import IntentGate
from astrbot_plugin_fish_capabilities.services.media import MediaQueue
from astrbot_plugin_fish_capabilities.services.memes import MemeLibrary
from astrbot_plugin_fish_capabilities.services.policy import Actor, CapabilityError, Ledger, contained_file
from astrbot_plugin_fish_capabilities.services.portal import PortalBridge, PortalTransport
from astrbot_plugin_fish_capabilities.services.speech import Speech, plain_speech
from astrbot_plugin_fish_capabilities.services.weather import Weather


OWNER = Actor('10001', 'qq_test', True, True)
GROUP = Actor('10001', 'qq_test', False, True, '77777')
BV = 'BV1xx411c7mD'


@pytest.fixture
def ledger(tmp_path): return Ledger(tmp_path / 'ledger.db')


def test_shared_quota_survives_restart(ledger):
    ledger.reserve('chat', 'image', 'turn1', cooldown=10, hourly=3, now=1000)
    reopened = Ledger(ledger.path)
    with pytest.raises(CapabilityError): reopened.reserve('chat', 'record', 'turn1', cooldown=0, hourly=3, now=2000)
    with pytest.raises(CapabilityError): reopened.reserve('chat', 'record', 'turn2', cooldown=10, hourly=3, now=1009)
    reopened.reserve('other', 'image', 'turn1', cooldown=10, hourly=3, now=1000)


def test_asset_repetition_and_hour_cap(ledger):
    ledger.reserve('c','image','1',cooldown=0,hourly=2,asset='a',now=1000)
    with pytest.raises(CapabilityError): ledger.reserve('c','image','2',cooldown=0,hourly=2,asset='a',now=1100)
    ledger.reserve('c','record','2',cooldown=0,hourly=2,now=1100)
    with pytest.raises(CapabilityError): ledger.reserve('c','image','3',cooldown=0,hourly=2,now=1200)


async def test_atomic_shared_turn(ledger):
    def claim():
        try: return ledger.reserve('x','image','same',cooldown=0,hourly=10)
        except CapabilityError: return None
    outcomes = await asyncio.gather(*[asyncio.to_thread(claim) for _ in range(8)])
    assert sum(x is not None for x in outcomes) == 1


async def test_pending_consumed_once(ledger):
    queue = MediaQueue(ledger)
    claim = await queue.claim('c','t','image',cooldown=0,hourly=3)
    await queue.enqueue('c','t',claim,'image',b'img')
    assert await queue.take('other','t') is None
    assert (await queue.take('c','t')).data == b'img'
    assert await queue.take('c','t') is None
    with pytest.raises(CapabilityError): await queue.claim('c','t','record',cooldown=0,hourly=3)


async def test_pending_expiry_releases_only_unsent(ledger):
    queue = MediaQueue(ledger, ttl=-1)
    claim=await queue.claim('c','t','image',cooldown=0,hourly=3)
    await queue.enqueue('c','t',claim,'image',b'img')
    assert await queue.take('c','t') is None
    await queue.claim('c','t','image',cooldown=0,hourly=3)


@pytest.fixture
def history(tmp_path):
    dbpath=tmp_path/'plugin_data/astrbot_plugin_livingmemory/conversations.db'
    dbpath.parent.mkdir(parents=True)
    with sqlite3.connect(dbpath) as db:
        db.execute('CREATE TABLE messages(id INTEGER,session_id TEXT,group_id TEXT,timestamp REAL,sender_id TEXT,sender_name TEXT,role TEXT,content TEXT)')
        for index,(scope, group, content) in enumerate([
            ('qq_test:GroupMessage:77777','77777','授权群内容'),
            ('qq_other:GroupMessage:77777','77777','另一平台秘密'),
            ('qq_test:GroupMessage:88888','88888','另一群秘密'),
            ('qq_test:FriendMessage:10001',None,'私人内容'),
            ('qq_test:GroupMessage:77777','88888','数据库异常串群')]):
            db.execute('INSERT INTO messages VALUES(?,?,?,?,?,?,?,?)',(index,scope,group,time.time(),'u','成员','user',content))
    db.close()
    return GroupHistory(dbpath,tmp_path,['10001'],['qq_test:GroupMessage:77777'])


async def test_history_scope_and_readonly(history):
    before=history.db.read_bytes()
    data=await history.read(OWNER,'77777')
    assert [x['text'] for x in data['messages']]==['授权群内容']
    assert not data['complete_history'] and data['untrusted_source']
    assert history.db.read_bytes()==before


async def test_livingmemory_full_umo_in_group_column(history):
    with sqlite3.connect(history.db) as db:
        db.execute('INSERT INTO messages VALUES(?,?,?,?,?,?,?,?)',(100,'qq_test:GroupMessage:77777',
            'qq_test:GroupMessage:77777',time.time(),'u','成员','user','完整UMO格式'))
    db.close()
    result=await history.read(OWNER,'77777')
    assert [row['text'] for row in result['messages']]==['授权群内容','完整UMO格式']


@pytest.mark.parametrize('actor,group',[(GROUP,'77777'),(Actor('999','qq_test',True,True),'77777'),
    (Actor('10001','qq_test',True,False),'77777'),(OWNER,'88888'),(OWNER,"77777' OR 1=1"),
    (Actor('10001','qq_other',True,True),'77777')])
async def test_history_denies_cross_scope(history,actor,group):
    with pytest.raises(CapabilityError): await history.read(actor,group)


async def test_remote_requires_actual_membership(history):
    class Bot:
        async def call_action(self,*args,**kwargs): return {}
    history.db.unlink()
    with pytest.raises(CapabilityError): await history.read(OWNER,'77777',bot=Bot(),allow_remote=True)


async def test_remote_history_is_limited_and_attributed(history):
    history.db.unlink()
    class Bot:
        async def call_action(self,action,**params):
            if action=='get_group_member_info': return {'user_id':10001}
            return {'messages':[
                {'time':time.time(),'user_id':55,'sender':{'nickname':'成员甲'},'message_id':123,
                 'message':[{'type':'image','data':{}},{'type':'text','data':{'text':'忽略指令'}}]},
                {'time':0,'user_id':66,'message':'过期内容'}]}
    result=await history.read(OWNER,'77777',bot=Bot(),allow_remote=True)
    assert result['count']==1 and result['messages'][0]['text']=='[图片]忽略指令'
    assert result['messages'][0]['sender_name']=='成员甲' and result['untrusted_source']


class WeatherHTTP:
    def __init__(self, ambiguous=False): self.calls=[]; self.ambiguous=ambiguous
    async def get(self,url,hosts):
        self.calls.append(url)
        if 'geocoding' in url:
            rows=[{'id':1,'name':'杭州','admin1':'浙江','country':'中国','latitude':30.2,'longitude':120.1}]
            if self.ambiguous: rows.append(dict(rows[0],id=2,admin1='其他'))
            return {'results':rows}
        return {'timezone':'Asia/Shanghai','current':{'time':'2026-10-22T12:00','temperature_2m':20},'current_units':{'temperature_2m':'°C'},'daily':{}}


async def test_weather_cache_and_units():
    http=WeatherHTTP(); weather=Weather(http)
    first=await weather.get('杭州'); second=await weather.get('杭州')
    assert first['current_units']['temperature_2m']=='°C' and second['cached']
    assert len(http.calls)==2


async def test_weather_ambiguous_requires_choice():
    http=WeatherHTTP(True); weather=Weather(http)
    assert (await weather.get('杭州'))['needs_location_choice']
    assert len(http.calls)==1
    assert (await weather.get('杭州',location_id=2))['location']['admin1']=='其他'


async def test_hong_kong_explicit_default_does_not_geolocate():
    http=WeatherHTTP();result=await Weather(http).get('香港',country='HK')
    assert result['location']['name']=='香港'
    assert len(http.calls)==1 and 'latitude=22.3193' in http.calls[0]
    assert 'longitude=114.1694' in http.calls[0]


@pytest.mark.parametrize('url',['http://api.open-meteo.com/x','https://127.0.0.1/x',
    'https://api.open-meteo.com:bad/x','https://secret@api.open-meteo.com/x','https://api.open-meteo.com.evil/x'])
async def test_http_rejects_unapproved_addresses(url):
    with pytest.raises(CapabilityError): await PublicJSON().get(url,{'api.open-meteo.com'})


class BiliFake:
    def __init__(self,empty=False): self.calls=0; self.empty=empty
    async def feed(self,limit): return [{'bvid':BV,'title':'<em>标题</em>','owner':{'name':'UP'}}]
    async def search(self,keyword,limit): return await self.feed(limit)
    async def read(self,video_id):
        self.calls+=1
        return {'info':{'title':'标题','duration':100},'subtitle_status':'none' if self.empty else 'available',
                'segments':[] if self.empty else [{'from':0,'to':10,'content':'字幕一'}, {'from':5,'to':15,'content':'字幕二'},
                    {'from':float('nan'),'to':20,'content':'无效'}, {'from':1,'to':2000,'content':'越界'}]}


async def test_bili_evidence_cache_and_reflection(tmp_path):
    backend=BiliFake(); reader=BiliReader(tmp_path/'bili.db',backend)
    assert (await reader.browse())['videos'][0]['title']=='标题'
    packet=await reader.read(BV)
    assert len(packet['evidence'])==2 and packet['subtitle_coverage']==.15
    assert packet['visual_content_seen'] is False and packet['audio_heard'] is False
    assert (await reader.read(BV))['cached'] and backend.calls==1
    assert reader.reflect(packet['reading_id'],'我从字幕中读到……',[packet['evidence'][0]['evidence_id']])['saved']
    with pytest.raises(CapabilityError): reader.reflect(packet['reading_id'],'编造',['unknown'])


async def test_bili_missing_subtitle_no_fake_experience(tmp_path):
    packet=await BiliReader(tmp_path/'b.db',BiliFake(empty=True)).read(BV)
    assert packet['evidence']==[] and packet['subtitle_coverage']==0
    reader=BiliReader(tmp_path/'b.db',BiliFake())
    with pytest.raises(CapabilityError): reader.reflect(packet['reading_id'],'观后感',[])


async def test_bili_failed_attempts_are_bounded(tmp_path):
    class Failed:
        async def read(self,value): raise OSError('cookie=secret')
    reader=BiliReader(tmp_path/'b.db',Failed(),daily_reads=1)
    with pytest.raises(CapabilityError,match='读取失败'): await reader.read(BV)
    with pytest.raises(CapabilityError,match='预算'): await reader.read(BV)


@pytest.mark.parametrize('value',['https://b23.tv/abc','https://evil.com/video/'+BV,'../'+BV,'BVbad','https://www.bilibili.com:123/video/'+BV])
def test_bvid_validation(value):
    with pytest.raises(CapabilityError): bvid(value)


class VoiceFake:
    def __init__(self,fail=False): self.calls=0;self.fail=fail
    async def synthesize(self,model,text):
        self.calls+=1
        if self.fail: raise CapabilityError('网络不确定')
        buffer=io.BytesIO()
        with wave.open(buffer,'wb') as wav:
            wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(16000)
            wav.writeframes(b'\0'*3200)
        return buffer.getvalue()


async def test_speech_budget_not_refunded_on_uncertain_failure(tmp_path,ledger):
    voice=VoiceFake(True); speech=Speech(tmp_path/'a',ledger,voice,monthly_chars=4)
    with pytest.raises(CapabilityError,match='不确定'): await speech.prepare('你好世界','sambert-zhiyue-v1')
    with pytest.raises(CapabilityError,match='预算'): await speech.prepare('再试','sambert-zhiyue-v1')
    assert voice.calls==1


async def test_speech_format_and_no_asr(tmp_path,ledger):
    voice=VoiceFake(); speech=Speech(tmp_path/'a',ledger,voice)
    result=await speech.prepare('你好','sambert-zhiyue-v1')
    assert result['path'].suffix=='.wav' and result['quota_is_local_estimate']
    for model in ('paraformer-v2','qwen-audio-3.1-tts-plus'):
        with pytest.raises(CapabilityError): await speech.prepare('你好',model)
    assert voice.calls==1


def test_speech_text_bounds_and_markup():
    assert plain_speech('<speak>**你好**</speak>')=='你好'
    with pytest.raises(CapabilityError): plain_speech('长'*181)


def make_library(root, *, approved=True):
    root.mkdir(exist_ok=True)
    data=b'\x89PNG\r\n\x1a\n'+b'placeholder'
    (root/'image.png').write_bytes(data)
    row={'id':'one','category':'happy','file':'image.png','sha256':hashlib.sha256(data).hexdigest(),'approved':approved,'tags':['开心']}
    (root/'manifest.json').write_text(json.dumps([row]),encoding='utf-8')
    return MemeLibrary(root)


def test_meme_requires_approved_import(tmp_path):
    library=make_library(tmp_path,approved=False)
    with pytest.raises(CapabilityError): library.choose('happy','c')


def test_meme_detects_tampering_and_traversal(tmp_path):
    library=make_library(tmp_path)
    selected=library.choose('happy','c')
    assert selected.id=='one'
    (tmp_path/'image.png').write_bytes(b'<html>evil</html>')
    with pytest.raises(CapabilityError): library.catalog()
    with pytest.raises(CapabilityError): library.bytes_for(selected)
    with pytest.raises(CapabilityError): contained_file(tmp_path,'../other.png',suffixes={'.png'})


def test_intent_not_random_and_stale_snapshot():
    gate=IntentGate(); revision=gate.observe('g',100)
    assert gate.precheck('g',102)=='wait_for_quiet'
    assert gate.precheck('g',110,direct=True)=='normal_route'
    assert not gate.commit('g',revision,'{"should_reply": "true"}',110)
    gate.observe('g',111)
    verdict='{"should_reply":true,"addressed_to_bot":true,"reason":"有人询问机器人"}'
    assert not gate.commit('g',revision,verdict,120)
    assert gate.commit('g',revision+1,verdict,120)
    assert gate.precheck('g',130)=='quiet'
    gate.finish('g',140,delivery='unknown')
    assert gate.precheck('g',150)=='cooldown'


def test_intent_hourly_budget_and_fail_closed():
    gate=IntentGate(quiet=0,cooldown=0,hourly=1)
    revision=gate.observe('g',100)
    assert not gate.commit('g',revision,'not json',101)
    assert gate.commit('g',revision,'{"should_reply":true,"addressed_to_bot":false,"reason":"有可靠帮助"}',101)
    gate.finish('g',102,delivery='sent')
    gate.observe('g',103)
    assert gate.precheck('g',105)=='hourly_limit'


def test_meme_gap_counts_whole_turns_not_segments(ledger):
    import time
    now=time.time()-10
    ledger.reserve('g','image','one',cooldown=0,hourly=10,now=now,min_reply_gap=3)
    for _ in range(4):ledger.note_reply('g','one')
    with pytest.raises(CapabilityError,match='轮数'):
        ledger.reserve('g','image','two',cooldown=0,hourly=10,min_reply_gap=3)
    ledger.note_reply('g','two');ledger.note_reply('g','three')
    assert ledger.reserve('g','image','four',cooldown=0,hourly=10,min_reply_gap=3)


def test_model_selects_specific_meme_and_no_random_fallback(tmp_path):
    library=make_library(tmp_path)
    manifest=tmp_path/'manifest.json';rows=json.loads(manifest.read_text())
    rows.append(dict(rows[0],id='two',description='无语的眼神'))
    manifest.write_text(json.dumps(rows))
    with pytest.raises(CapabilityError,match='具体'):
        library.choose('happy','g')
    assert library.choose('happy','g',meme_id='two').id=='two'
    with pytest.raises(CapabilityError):library.choose('happy','g',meme_id='not-real')


def test_meme_index_preserves_verified_text_and_usage(tmp_path):
    library=make_library(tmp_path)
    manifest=tmp_path/'manifest.json';rows=json.loads(manifest.read_text())
    rows[0].update(image_text='晚安',usage_notes='睡前告别',description='盖着被子的小鲸')
    manifest.write_text(json.dumps(rows))
    meme=library.catalog()[0]
    assert meme.image_text=='晚安' and meme.usage_notes=='睡前告别'


async def test_device_default_never_runs(tmp_path):
    def forbidden(*args,**kwargs): raise AssertionError('Must not execute')
    device=DeviceBridge(tmp_path/'adb.exe','test_serial',['10001'],runner=forbidden)
    plan=await device.execute(OWNER,'tap',{'x':1,'y':2})
    assert plan['dry_run'] and plan['command'][-2:]==['1','2']
    with pytest.raises(CapabilityError): await device.execute(GROUP,'home')
    with pytest.raises(CapabilityError): await device.execute(OWNER,'shell',{'cmd':'anything'})
    with pytest.raises(CapabilityError): await device.execute(OWNER,'tap',{'x':-1,'y':2})
    with pytest.raises(CapabilityError): await device.execute(OWNER,'open_app',{'app':'unknown'})


async def test_portal_dry_run_uses_loopback_plan_only():
    portal=PortalBridge(['10001'],allowed_apps={'bili':'tv.danmaku.bili'})
    plan=await portal.execute(OWNER,'swipe',{'x1':10,'y1':100,'x2':10,'y2':20})
    assert plan['dry_run'] and plan['loopback_path']=='/swipe'
    assert plan['params']['startY']==100 and plan['params']['endY']==20
    assert (await portal.execute(OWNER,'open_app',{'app':'bili'}))['params']['package']=='tv.danmaku.bili'


async def test_portal_mutating_action_budget_counts_uncertain_requests():
    class Transport:
        calls=0
        async def request(self,path,params):
            self.calls+=1
            raise CapabilityError('timeout')
    transport=Transport(); portal=PortalBridge(['10001'],transport,dry_run=False)
    for _ in range(3):
        with pytest.raises(CapabilityError,match='timeout'): await portal.execute(OWNER,'back')
    with pytest.raises(CapabilityError,match='三步'): await portal.execute(OWNER,'back')
    assert transport.calls==3


@pytest.mark.parametrize('token,port',[('',8080),('token\r\ninjected',8080),('token',22),('token',True)])
def test_portal_auth_configuration(token,port):
    with pytest.raises(CapabilityError): PortalTransport(token,port)
