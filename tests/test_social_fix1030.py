from unittest.mock import AsyncMock
import pytest
from test_bili_comments import prepared
from test_bili_dynamic_replies import make_worker
from astrbot_plugin_fish_capabilities.services.policy import CapabilityError

async def test_video_owner_reply_has_target_and_independent_dedup(tmp_path):
    reader,p,w=await prepared(tmp_path);w.settings.update(bili_owner_uid='7',bili_comment_interval_seconds=0,bili_comment_daily_limit=20)
    w.backend.reply_location=AsyncMock(return_value={'root':'201','parent':'201'})
    w.backend.send=AsyncMock(return_value={'reply_id':'999','aid':456})
    ids=[p['evidence'][0]['evidence_id']];target={'id':'201','author':'7'}
    await w.post(p['reading_id'],'这里挺有意思',ids,reply_to=target)
    assert w.backend.send.call_args.kwargs['reply_to']==target
    with pytest.raises(CapabilityError):await w.post(p['reading_id'],'不重复发',ids,reply_to=target)
    with pytest.raises(CapabilityError):await w.post(p['reading_id'],'不能回复他人任务',ids,reply_to={'id':'202','author':'8'})
    assert w.backend.send.await_count==1

async def test_pause_does_not_consume_new_dynamic_comment(tmp_path):
    w,b,r,j,t,row=await make_worker(tmp_path)
    with w.reader.connect() as db:db.execute('INSERT INTO bili_comment_pause VALUES(?,?)',('42','test'))
    assert (await w.check())['state']=='comments_paused'
    with w.reader.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM dynamic_reply_items').fetchone()[0]==0
        db.execute('DELETE FROM bili_comment_pause')
    assert (await w.check())['submitted']==1
