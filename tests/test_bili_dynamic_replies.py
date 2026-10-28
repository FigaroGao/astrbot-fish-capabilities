import types
from unittest.mock import AsyncMock
import pytest
from test_bili_activity import make
from astrbot_plugin_fish_capabilities.services.bili_comments import BiliComments
from astrbot_plugin_fish_capabilities.services.bili_dynamic_replies import DynamicReplies
from astrbot_plugin_fish_capabilities.services.policy import CapabilityError


async def make_worker(tmp_path):
    a,b,r,g,n,t,c=make(tmp_path)
    a.config.update(bili_dynamic_reply_enabled=True,bili_comment_enabled=True,bili_owner_uid='7',bili_comment_daily_limit=20,bili_comment_interval_seconds=0)
    comments=BiliComments(a.reader,a.config,clock=lambda:t[0]);comments.reviewer=r
    resource={'post':'12345','author':'42','oid':'12345','type':17}
    row={'rpid':'201','root':0,'member':{'mid':'7'},'content':{'message':'这条有意思哈哈'},'ctime':t[0]+1}
    backend=types.SimpleNamespace(identity=AsyncMock(return_value='42'),resource=AsyncMock(return_value=resource),comments=AsyncMock(side_effect=lambda resource,page:[row] if page==1 else []),send=AsyncMock(return_value='999'))
    judge=AsyncMock(return_value={'decision':'reply','text':'哈哈，我也是看到这里笑了'})
    worker=DynamicReplies(a.reader,comments,a.config,judge,backend,clock=lambda:t[0])
    with a.reader.connect() as db:db.execute('INSERT INTO bili_dynamic_posts VALUES(?,?,?,?,?,?)',('post','42',t[0]-100,'submitted','12345','公开碎碎念'))
    t[0]+=2
    return worker,backend,r,judge,t,row


async def test_owner_new_comment_replied_reviewed_shared_budget_and_restart_dedup(tmp_path):
    w,b,r,j,t,row=await make_worker(tmp_path)
    result=await w.check();assert result['submitted']==1
    r.gate.assert_awaited_once();assert b.send.call_args.args[1:3]==('201','201')
    with w.reader.connect() as db:assert db.execute("SELECT COUNT(*) FROM bili_comments WHERE state='submitted'").fetchone()[0]==1
    t[0]+=601;await DynamicReplies(w.reader,w.comments,w.config,j,b,clock=lambda:t[0]).check();assert b.send.await_count==1


@pytest.mark.parametrize('condition',['other_author','old_comment','wrong_post_owner','task','review_denied','no_permission'])
async def test_dynamic_reply_boundaries(tmp_path,condition):
    w,b,r,j,t,row=await make_worker(tmp_path)
    if condition=='other_author':row['member']['mid']='99'
    if condition=='old_comment':row['ctime']=t[0]-9999
    if condition=='wrong_post_owner':b.resource.return_value['author']='99'
    if condition=='task':row['content']['message']='帮我算一下 125*46'
    if condition=='review_denied':r.gate.side_effect=CapabilityError('denied')
    if condition=='no_permission':w.config['bili_dynamic_reply_enabled']=False
    await w.check();b.send.assert_not_called()
    if condition in ('task','other_author','old_comment','wrong_post_owner','no_permission'):j.assert_not_called()


async def test_dynamic_uncertain_send_is_not_replayed_and_freezes_shared_writes(tmp_path):
    w,b,r,j,t,row=await make_worker(tmp_path);b.send.side_effect=TimeoutError()
    await w.check();t[0]+=601;await w.check();assert b.send.await_count==1
    with w.reader.connect() as db:
        assert db.execute("SELECT state FROM dynamic_reply_items").fetchone()[0]=='uncertain'
        assert db.execute("SELECT state FROM bili_comments").fetchone()[0]=='pending'


async def test_dynamic_comment_changed_before_write_is_not_sent(tmp_path):
    w,b,r,j,t,row=await make_worker(tmp_path)
    async def review(*args):row['content']['message']='changed after review'
    r.gate.side_effect=review
    await w.check();b.send.assert_not_called()


async def test_dynamic_replies_share_existing_daily_cap(tmp_path):
    w,b,r,j,t,row=await make_worker(tmp_path);w.config['bili_comment_daily_limit']=1
    with w.reader.connect() as db:db.execute('INSERT INTO bili_comments VALUES(?,?,?,?,?,?,?)',('used','42','',t[0],'submitted','111','hash'))
    await w.check();b.send.assert_not_called()
