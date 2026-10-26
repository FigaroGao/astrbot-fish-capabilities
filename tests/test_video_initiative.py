from datetime import datetime,timezone,timedelta
import json
import pytest
from test_services import BiliFake,BV
from astrbot_plugin_fish_capabilities.services.bilibili import BiliReader
from astrbot_plugin_fish_capabilities.services.bili_consent import Consent
from astrbot_plugin_fish_capabilities.services.bili_preview import positions
from astrbot_plugin_fish_capabilities.services.private_initiative import Initiative
from astrbot_plugin_fish_capabilities.services.policy import CapabilityError

async def test_over_ten_minutes_rejected_without_memory(tmp_path):
    class Long(BiliFake):
        async def read(self,video):
            p=await super().read(video);p['info']['duration']=601;return p
    r=BiliReader(tmp_path/'b.db',Long())
    with pytest.raises(CapabilityError,match='10分钟'):await r.read(BV)
    assert r.memory.search()['total_videos']==0

def test_preview_nine_spread_samples():
    selected=positions(list(range(0,601,10)),600)
    assert len(selected)==9 and selected[0][1]<60 and selected[-1][1]>540

async def test_consent_bound_to_owner_scope_and_single_use(tmp_path):
    c=Consent(BiliReader(tmp_path/'b.db',BiliFake()));code=c.request('owner','group-a',BV)
    for owner,group in [('other','group-a'),('owner','group-b')]:
        with pytest.raises(CapabilityError):c.consume(owner,group,'确认看视频 '+code)
    assert c.consume('owner','group-a','确认看视频 '+code)==BV
    with pytest.raises(CapabilityError):c.consume('owner','group-a','确认看视频 '+code)

async def make_ping(tmp_path,hour=10):
    clock=[datetime(2026,10,24,hour,tzinfo=timezone(timedelta(hours=8))).timestamp()];sent=[];calls=[]
    async def generate(prompt):calls.append(prompt);return json.dumps({'send':True,'message':'下课了吗？'})
    async def deliver(text):sent.append(text)
    p=Initiative(tmp_path/'private.db',generate,deliver,clock=lambda:clock[0])
    return p,clock,sent,calls

async def test_class_one_hour_quiet_two_hours_can_ask(tmp_path):
    p,t,sent,calls=await make_ping(tmp_path);p.observe('我去上课了');t[0]+=3600
    assert await p.tick()=='busy' and not calls
    t[0]+=3600
    assert await p.tick()=='sent' and sent==['下课了吗？']
    assert await p.tick()=='recent_conversation'

async def test_limits_persist_across_restart(tmp_path):
    p,t,sent,calls=await make_ping(tmp_path);p.offer('一个有趣的视频')
    assert await p.tick()=='sent'
    t[0]+=2*3600;assert await p.tick()=='cooldown'
    t[0]+=3600;assert await p.tick()=='sent'
    t[0]+=3*3600
    other=Initiative(p.path,p.generate,p.deliver,p.clock)
    assert await other.tick()=='daily_limit' and len(sent)==2

async def test_quiet_hours_and_sleep(tmp_path):
    p,t,sent,calls=await make_ping(tmp_path,23);p.offer('视频')
    assert await p.tick()=='quiet_hours'
    p,t,sent,calls=await make_ping(tmp_path,10);p.observe('我去睡觉了');t[0]+=2*3600
    assert await p.tick()=='busy' and not sent

async def test_new_message_during_judgement_cancels_send(tmp_path):
    p,t,sent,calls=await make_ping(tmp_path);p.offer('视频')
    async def generate(prompt):t[0]+=1;p.observe('先别找我');return '{"send":true,"message":"hi"}'
    p.generate=generate
    assert await p.tick()=='new_activity' and not sent

async def test_judgement_failure_does_not_send_or_retry_hour(tmp_path):
    p,t,sent,calls=await make_ping(tmp_path);p.offer('视频')
    async def generate(prompt):raise TimeoutError()
    p.generate=generate
    assert await p.tick()=='judge_failed'
    assert await p.tick()=='already_judged' and not sent


def test_natural_consent_unique_scoped_and_ambiguous(tmp_path):
    c=Consent(BiliReader(tmp_path/'consent.db',BiliFake()))
    assert c.request('owner','group-a',BV)
    assert c.request('owner','group-a',BV) is None
    for owner,scope in [('other','group-a'),('owner','group-b')]:
        with pytest.raises(CapabilityError):c.approve(owner,scope)
    second='BV1234567890'
    c.request('owner','group-a',second)
    with pytest.raises(CapabilityError,match='多个'):c.approve('owner','group-a')
    assert c.approve('owner','group-a',BV)==BV
    assert c.approve('owner','group-a')==second
    with pytest.raises(CapabilityError):c.approve('owner','group-a')


async def test_initiative_records_silence_and_errors(tmp_path):
    p,t,sent,calls=await make_ping(tmp_path);p.offer('话题')
    async def quiet(prompt):return '{"send":false,"message":""}'
    p.generate=quiet
    assert await p.tick()=='chose_silence'
    with p.db() as db:assert db.execute('SELECT state FROM decisions').fetchone()[0]=='chose_silence'
    t[0]+=3600
    async def fail(prompt):raise TimeoutError('sensitive detail')
    p.generate=fail
    assert await p.tick()=='judge_failed'
    data=json.loads(p.path.with_name('private-initiative-status.json').read_text())
    assert data['error_type']=='TimeoutError' and 'sensitive' not in str(data)
    with p.db() as db:assert db.execute('SELECT state FROM decisions ORDER BY stamp DESC').fetchone()[0]=='judge_failed'
    assert not sent


def test_preview_twenty_seven_spread_and_deduplicated():
    assert len(positions(list(range(601)),600,27))==27
    assert len(positions([0,60],60,27))==2

async def test_activity_memory_private_short_lived_and_completion(tmp_path):
    p,t,sent,calls=await make_ping(tmp_path)
    record={'activity_note':'推测主人还在上课，暂不打扰','pending_note':'找机会分享鲸鱼视频','pending_after_hours':2}
    p.remember_activity(record,'chose_silence')
    notes=p.activities();assert len(notes)==2
    pending=next(n for n in notes if n['kind']=='pending')
    assert not pending['done'] and pending['earliest_contact_at']==t[0]+7200
    p.remember_activity({'pending_note':record['pending_note']},'chose_silence')
    assert len(p.activities())==2
    p.remember_activity({'complete_activity_ids':[pending['id']]},'chose_silence')
    assert not next(n for n in p.activities() if n['kind']=='pending')['done']
    p.remember_activity({'complete_activity_ids':[pending['id']]},'sent')
    assert next(n for n in p.activities() if n['kind']=='pending')['done']
    t[0]+=73*3600;assert p.activities()==[]

async def test_activity_memory_is_supplied_to_next_decision(tmp_path):
    p,t,sent,calls=await make_ping(tmp_path)
    p.remember_activity({'pending_note':'之后分享一段海洋视频'},'chose_silence');p.offer('话题')
    await p.tick()
    assert '之后分享一段海洋视频' in calls[0] and 'private_activity_memory' in calls[0]

async def test_selected_frame_budget_cache_and_validation(tmp_path):
    r=BiliReader(tmp_path/'frames.db',BiliFake());seen=[]
    async def visual(packet,info):
        seen.append(packet['preview_requested']);return {'visual_status':'sampled_preview','preview_layout_version':2,'preview_frames':packet['preview_requested']}
    r.visual_reader=visual
    assert (await r.read(BV,frame_count=18))['preview_frames']==18
    assert (await r.read(BV,frame_count=9))['cached']
    assert (await r.read(BV,frame_count=27))['preview_frames']==27
    assert seen==[18,27]
    with pytest.raises(CapabilityError):await r.read(BV,frame_count=28)


def test_twenty_seven_preview_panels_make_three_sheets(tmp_path,monkeypatch):
    import io
    from PIL import Image
    from astrbot_plugin_fish_capabilities.services.bili_preview import Preview
    import urllib.request
    buffer=io.BytesIO();Image.new('RGB',(180,60),'blue').save(buffer,format='PNG');data=buffer.getvalue()
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,n):return data
    class Opener:
        def open(self,*args,**kwargs):return Response()
    monkeypatch.setattr(urllib.request,'build_opener',lambda *args:Opener())
    info={'img_x_len':9,'img_y_len':3,'img_x_size':20,'img_y_size':20,'image':['https://i0.hdslb.com/test.png']}
    result=Preview(tmp_path/'previews').build(BV,info,[(i,float(i)) for i in range(27)])
    assert result['frames']==27 and len(result['paths'])==3
    assert all(p.exists() for p in result['paths'])


@pytest.mark.parametrize('size',[(480,270),(270,480)])
def test_preview_preserves_native_pixels_and_adapts_four_frame_layout(tmp_path,monkeypatch,size):
    import io,urllib.request
    from PIL import Image
    from astrbot_plugin_fish_capabilities.services.bili_preview import Preview
    w,h=size
    image=Image.new('RGB',(w*4,h),'white')
    for x in range(0,w*4,2):
        for y in range(h):image.putpixel((x,y),(0,0,0))
    buf=io.BytesIO();image.save(buf,format='PNG');raw=buf.getvalue()
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,n):return raw
    class Opener:
        def open(self,*args,**kwargs):return Response()
    monkeypatch.setattr(urllib.request,'build_opener',lambda *a:Opener())
    result=Preview(tmp_path).build(BV,{'img_x_len':4,'img_y_len':1,'img_x_size':w,'img_y_size':h,'image':['https://i0.hdslb.com/test.png']},[(i,float(i)) for i in range(4)])
    output=Image.open(result['path'])
    assert output.size==(w*2,(h+26)*2)
    assert output.crop((0,0,w,h)).tobytes()==image.crop((0,0,w,h)).tobytes()
    assert result['source_frame_size']==result['sent_frame_size']==[w,h]
