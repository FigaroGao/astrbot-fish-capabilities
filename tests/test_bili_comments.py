import json
import pytest
from test_services import BiliFake, BV
from astrbot_plugin_fish_capabilities.services.bilibili import BiliReader
from astrbot_plugin_fish_capabilities.services.bili_comments import BiliComments
from astrbot_plugin_fish_capabilities.services.bili_duty import BiliDuty
from astrbot_plugin_fish_capabilities.services.policy import CapabilityError

class Posting:
    def __init__(self, fail=False, identity='42'):
        self.fail=fail;self.who=identity;self.calls=0
    async def identity(self): return self.who
    async def send(self,video_id,text):
        self.calls+=1
        if self.fail:raise TimeoutError('secret credential must never appear')
        return {'reply_id':'123','aid':456}
    async def verify(self,*args):return True
    async def verify_public(self,*args):return True

async def prepared(tmp_path,backend=None):
    reader=BiliReader(tmp_path/'b.db',BiliFake())
    packet=await reader.read(BV)
    config={'bili_comment_enabled':True,'bili_account_id':'42'}
    writer=BiliComments(reader,config,backend or Posting())
    return reader,packet,writer

async def test_comment_once_and_duplicate_survives_reinitialization(tmp_path):
    reader,p,w=await prepared(tmp_path)
    evidence=[p['evidence'][0]['evidence_id']]
    assert (await w.post(p['reading_id'],'字幕中的讨论很有意思。',evidence))['publicly_visible_verified']
    other=BiliComments(reader,w.settings,w.backend)
    with pytest.raises(CapabilityError,match='不重复'):await other.post(p['reading_id'],'换个文本也不能重复。',evidence)
    assert w.backend.calls==1

async def test_comment_timeout_pauses_all_later_posts(tmp_path):
    reader,p,w=await prepared(tmp_path,Posting(fail=True))
    with pytest.raises(CapabilityError,match='已暂停') as exc:await w.post(p['reading_id'],'想法不错。',[p['evidence'][0]['evidence_id']])
    assert 'secret' not in str(exc.value)
    assert w.status()['paused']
    assert w.status()['receipts']=={'uncertain':1}
    assert BiliComments(reader,w.settings,w.backend).status()['paused']

@pytest.mark.parametrize('case',['disabled','account_mismatch','no_evidence','invented_evidence','private_data'])
async def test_comment_preconditions_never_send(tmp_path,case):
    _,p,w=await prepared(tmp_path)
    text='这个观点值得讨论。';evidence=[p['evidence'][0]['evidence_id']]
    if case=='disabled':w.settings['bili_comment_enabled']=False
    if case=='account_mismatch':w.backend.who='99'
    if case=='no_evidence':evidence=[]
    if case=='invented_evidence':evidence=['invented']
    if case=='private_data':text='SESSDATA=private'
    with pytest.raises(CapabilityError):await w.post(p['reading_id'],text,evidence)
    assert w.backend.calls==0

async def test_pending_reservation_prevents_new_writes(tmp_path):
    reader,p,w=await prepared(tmp_path)
    with reader.connect() as db:db.execute('INSERT INTO bili_comments VALUES(?,?,?,?,?,?,?)',('old','42','other',0,'pending','','hash'))
    with pytest.raises(CapabilityError,match='未确认'):await w.post(p['reading_id'],'不错。',[p['evidence'][0]['evidence_id']])
    assert w.backend.calls==0

async def test_duty_idempotent_and_recommendation_cites_real_video(tmp_path):
    reader,p,w=await prepared(tmp_path);w.settings['bili_comment_enabled']=False
    calls=[];sent=[]
    async def generate(prompt):
        calls.append(prompt)
        return json.dumps({'bvid':BV}) if len(calls)==1 else json.dumps({'recommend':True,'recommendation':'一个值得讨论的观点','comment':'','evidence_ids':[]})
    async def deliver(text):sent.append(text)
    duty=BiliDuty(reader,w,w.settings,generate,deliver)
    assert (await duty.once('test-slot'))['state']=='recommended'
    assert (await duty.once('test-slot'))['state']=='already_reserved'
    assert len(calls)==2 and len(sent)==1 and BV in sent[0]
    assert '未观看画面' in sent[0]

async def test_duty_rejects_model_invented_target(tmp_path):
    reader,p,w=await prepared(tmp_path)
    async def generate(prompt):return '{"bvid":"not-in-candidates"}'
    async def deliver(text):raise AssertionError('must not send')
    assert (await BiliDuty(reader,w,w.settings,generate,deliver).once('test'))['state']=='abstained'

async def test_duty_failed_run_is_not_retried(tmp_path):
    reader,p,w=await prepared(tmp_path);calls=[]
    async def generate(prompt):calls.append(prompt);raise TimeoutError()
    async def deliver(text):raise AssertionError()
    duty=BiliDuty(reader,w,w.settings,generate,deliver)
    with pytest.raises(TimeoutError):await duty.once('test')
    assert (await duty.once('test'))['state']=='already_reserved'
    assert len(calls)==1


async def test_browsing_batch_reads_three_but_shares_only_one(tmp_path):
    ids=[BV,'BV1234567890','BV0987654321']
    class Several(BiliFake):
        async def feed(self,limit):return [{'bvid':v,'title':'视频'+str(i),'duration':100} for i,v in enumerate(ids)]
    reader=BiliReader(tmp_path/'batch.db',Several());writer=BiliComments(reader,{'bili_comment_enabled':False},Posting())
    calls=[];sent=[]
    async def generate(prompt):
        calls.append(prompt)
        if len(calls)==1:return json.dumps({'bvids':ids,'frame_count':3})
        return json.dumps({'bvid':ids[1],'recommend':True,'recommendation':'这个点挺有意思的。你可能会喜欢！','summary':'简短事实','comment':''})
    async def deliver(text):sent.append(text)
    result=await BiliDuty(reader,writer,writer.settings,generate,deliver).once('batch')
    assert result['read_count']==3 and len(sent)==1 and ids[1] in sent[0]
    assert len(sent[0])<260 and '【小鲸的B站发现】' not in sent[0]
    assert reader.memory.search()['total_videos']==3


async def test_zero_interval_allows_recent_other_video_but_preserves_daily_limit(tmp_path):
    reader,p,w=await prepared(tmp_path);w.settings['bili_comment_interval_seconds']=0
    now=w.clock()
    with reader.connect() as db:db.execute('INSERT INTO bili_comments VALUES(?,?,?,?,?,?,?)',('recent','42','other',now-1,'visible','old-id','hash'))
    assert w.status()['comment_interval_seconds']==0
    result=await w.post(p['reading_id'],'有意思。',[p['evidence'][0]['evidence_id']])
    assert result['submitted'] and w.backend.calls==1
    # Two attempts already exist; another video remains blocked by the daily cap.
    second=await reader.read('BV1234567890')
    with pytest.raises(CapabilityError,match='滚动24小时最多2条'):
        await w.post(second['reading_id'],'另一个想法。',[second['evidence'][0]['evidence_id']])
    assert w.backend.calls==1


async def test_positive_comment_interval_still_enforced(tmp_path):
    reader,p,w=await prepared(tmp_path);w.settings['bili_comment_interval_seconds']=1800
    with reader.connect() as db:db.execute('INSERT INTO bili_comments VALUES(?,?,?,?,?,?,?)',('recent','42','other',w.clock()-1,'visible','old-id','hash'))
    with pytest.raises(CapabilityError,match='评论间隔'):
        await w.post(p['reading_id'],'有意思。',[p['evidence'][0]['evidence_id']])
    assert w.backend.calls==0


async def test_twenty_comment_budget_allows_twentieth_blocks_twenty_first(tmp_path):
    reader,p,w=await prepared(tmp_path)
    w.settings.update(bili_comment_interval_seconds=0,bili_comment_daily_limit=20)
    now=w.clock()
    with reader.connect() as db:
        db.executemany('INSERT INTO bili_comments VALUES(?,?,?,?,?,?,?)',[(str(i),'42','old-'+str(i),now-1,'visible','receipt','hash') for i in range(19)])
        db.execute('INSERT INTO bili_comments VALUES(?,?,?,?,?,?,?)',('expired','42','expired-video',now-86401,'visible','receipt','hash'))
    assert w.status()['daily_comment_limit']==20
    assert (await w.post(p['reading_id'],'第20条。',[p['evidence'][0]['evidence_id']]))['submitted']
    second=await reader.read('BV1234567890')
    with pytest.raises(CapabilityError,match='滚动24小时最多20条'):
        await w.post(second['reading_id'],'第21条不能发。',[second['evidence'][0]['evidence_id']])
    assert w.backend.calls==1
