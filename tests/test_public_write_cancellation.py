import asyncio
from unittest.mock import AsyncMock
import pytest
from test_bili_comments import prepared
from test_bili_replies import make_inbox
from test_bili_activity import make
from test_bili_dynamic_replies import make_worker
from astrbot_plugin_fish_capabilities.services.policy import CapabilityError


async def test_cancelled_root_transport_keeps_uncertain_receipt_and_pause(tmp_path):
    reader,packet,writer=await prepared(tmp_path)
    writer.backend.send=AsyncMock(side_effect=asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        await writer.post(packet['reading_id'],'这个画面挺有趣。',[packet['evidence'][0]['evidence_id']])
    assert writer.status()['paused'] and writer.status()['receipts']=={'uncertain':1}
    with pytest.raises(CapabilityError):
        await writer.post(packet['reading_id'],'另一句话。',[packet['evidence'][0]['evidence_id']])
    assert writer.backend.send.await_count==1


async def test_cancelled_nested_reply_is_not_stranded_as_sending(tmp_path):
    inbox,backend,*_=await make_inbox(tmp_path)
    backend.send=AsyncMock(side_effect=asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):await inbox.check()
    assert inbox.list()['replies'][0]['state']=='uncertain'
    assert inbox.comments.status()['paused']


async def test_cancelled_dynamic_is_uncertain_not_retried(tmp_path):
    activity,backend,*_=make(tmp_path)
    backend.post=AsyncMock(side_effect=asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):await activity.post('今天看到一只海鸟。')
    assert activity.posts()['items'][0]['state']=='uncertain'
    with pytest.raises(CapabilityError):await activity.post('另一条动态。')
    assert backend.post.await_count==1


async def test_cancelled_dynamic_reply_preserves_shared_write_freeze(tmp_path):
    worker,backend,*_=await make_worker(tmp_path)
    backend.send.side_effect=asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):await worker.check()
    with worker.reader.connect() as db:
        assert db.execute('SELECT state FROM dynamic_reply_items').fetchone()[0]=='uncertain'
        assert db.execute("SELECT COUNT(*) FROM bili_comments WHERE state='pending'").fetchone()[0]==1
