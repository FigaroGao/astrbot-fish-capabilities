import asyncio,json
import pytest
from test_video_initiative import make_ping


async def test_overlapping_tick_does_not_erase_inflight_activity_note(tmp_path):
    ping,clock,sent,calls=await make_ping(tmp_path)
    ping.offer('一条有趣的话题')
    entered=asyncio.Event();release=asyncio.Event()
    async def generate(prompt):
        calls.append(prompt)
        return json.dumps({'send':True,'message':'这个细节有点意思','activity_note':'分享了一个具体细节'})
    async def deliver(text):entered.set();await release.wait();sent.append(text)
    ping.generate=generate;ping.deliver=deliver
    first=asyncio.create_task(ping.tick());await entered.wait()
    assert await ping.tick()=='running'
    release.set();assert await first=='sent'
    assert len(calls)==1 and len(sent)==1
    assert ping.activities()[0]['note']=='分享了一个具体细节'


async def test_cancelled_generation_releases_lock_and_marks_decision_interrupted(tmp_path):
    ping,clock,sent,calls=await make_ping(tmp_path);ping.offer('素材')
    entered=asyncio.Event()
    async def generate(prompt):entered.set();await asyncio.Event().wait()
    ping.generate=generate
    task=asyncio.create_task(ping.tick());await entered.wait();task.cancel()
    with pytest.raises(asyncio.CancelledError):await task
    assert not ping.lock.locked()
    with ping.db() as db:assert db.execute('SELECT state FROM decisions').fetchone()[0]=='interrupted'
    assert not sent
