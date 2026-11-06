import asyncio
import importlib.util
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('brain',Path(__file__).parents[1]/'astrbot_plugin_fish_capabilities/services/brain.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
Brain=module.Brain

def test_atomic_cross_instance_claim_and_dedup(tmp_path):
    now=[1000.];a=Brain(tmp_path/'brain.db',lambda:now[0]);b=Brain(tmp_path/'brain.db',lambda:now[0])
    lease=a.claim('qq','topic1');assert lease
    assert not b.claim('desktop','topic2')
    a.finish(lease,True);assert not b.claim('desktop','topic2')
    now[0]+=121
    assert not b.claim('qq','topic1')
    assert b.claim('desktop','topic2')

def test_owner_preempts_inflight_and_mute(tmp_path):
    now=[1000.];b=Brain(tmp_path/'b.db',lambda:now[0])
    lease=b.claim('qq','a');assert b.valid(lease)
    b.observe('qq_owner_chat');assert not b.valid(lease)
    now[0]+=121;assert not b.valid(lease)
    b.mute(300);assert not b.available()
    now[0]+=301;assert b.available()

def test_expired_lease_and_restart(tmp_path):
    now=[1000.];b=Brain(tmp_path/'b.db',lambda:now[0]);old=b.claim('qq','a',10)
    now[0]+=11;b=Brain(tmp_path/'b.db',lambda:now[0])
    fresh=b.claim('desktop','a');assert fresh and not b.valid(old)
    b.finish(old,True);assert b.valid(fresh)

def test_work_state_is_bounded_recent_and_not_longterm(tmp_path):
    now=[1000.];b=Brain(tmp_path/'b.db',lambda:now[0]);b.work('bili','reading')
    assert b.snapshot()['working'][0]['state']=='reading'
    now[0]+=3601;assert b.snapshot()['working']==[]


def test_owner_input_is_an_observation_not_a_durable_activity_claim(tmp_path):
    now=[1000.];b=Brain(tmp_path/'b.db',lambda:now[0])
    b.observe('qq_owner_chat');now[0]+=121
    assert b.available()
    assert b.snapshot()['working'][0]=={'kind':'qq_owner_chat','state':'observed','at':1000.}
    with b.db() as db:db.execute('INSERT OR REPLACE INTO brain_work VALUES(?,?,?)',('desktop_owner_chat','active',now[0]))
    assert all(row['state']=='observed' for row in b.snapshot()['working'])

@pytest.mark.asyncio
async def test_decision_concurrency_preemption_and_recovery(tmp_path):
    b=Brain(tmp_path/'b.db',lambda:1000.)
    entered=asyncio.Event();release=asyncio.Event()
    async def slow():
        entered.set();await release.wait();return 'draft'
    task=asyncio.create_task(b.decide('owner',slow));await entered.wait()
    with pytest.raises(module.AttentionDeferred):await b.decide('owner',slow)
    # A group has no access to private working data and no owner-contact lock.
    async def group():return 'group'
    assert await b.decide('group:1',group,owner_attention=False)=='group'
    b.observe('owner');release.set()
    with pytest.raises(module.AttentionDeferred):await task
    with b.db() as db:assert not db.execute('SELECT * FROM brain_decisions').fetchall()

@pytest.mark.asyncio
async def test_failed_and_cancelled_models_release_decision(tmp_path):
    b=Brain(tmp_path/'b.db',lambda:1000.)
    async def fail():raise ValueError('model failed')
    with pytest.raises(ValueError):await b.decide('owner',fail)
    async def good():return 'ok'
    assert await b.decide('owner',good)=='ok'

@pytest.mark.asyncio
async def test_public_transport_guard_mute_concurrency_and_no_retry(tmp_path):
    b=Brain(tmp_path/'b.db',lambda:1000.)
    class Backend:
        calls=0
        async def send(self,text):self.calls+=1;return text
    backend=Backend();b.guard_backend(backend,'send');b.guard_backend(backend,'send')
    b.mute(100)
    with pytest.raises(module.AttentionDeferred):await backend.send('blocked')
    assert backend.calls==0
    b.mute(0);assert await backend.send('ok')=='ok';assert backend.calls==1
    async def broken():raise OSError('unknown result')
    with pytest.raises(OSError):await b.publish(broken)
    assert await backend.send('new event')=='new event'
    async def good():return 'ok'
    async def blocked():await asyncio.Event().wait()
    task=asyncio.create_task(b.decide('owner',blocked));await asyncio.sleep(0);task.cancel()
    with pytest.raises(asyncio.CancelledError):await task
    assert await b.decide('owner',good)=='ok'

def test_input_replay_does_not_extend_busy_or_revision(tmp_path):
    now=[1000.];b=Brain(tmp_path/'b.db',lambda:now[0])
    b.observe('owner','event1');first=b.snapshot()['attention']
    now[0]+=30;b.observe('owner','event1')
    assert b.snapshot()['attention']==first
    b.observe('owner','event2');assert b.snapshot()['attention']['revision']==first['revision']+1

def test_cross_thread_contact_claim_has_one_winner(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    a=Brain(tmp_path/'b.db',lambda:1000.);b=Brain(tmp_path/'b.db',lambda:1000.);barrier=Barrier(2)
    def claim(pair):
        obj,key=pair;barrier.wait();return obj.claim('contact',key)
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(claim,[(a,'qq'),(b,'desktop')]))
    assert sum(x is not None for x in results)==1

@pytest.mark.asyncio
async def test_expired_decision_result_is_rejected_after_replacement(tmp_path):
    now=[1000.];b=Brain(tmp_path/'brain.db',lambda:now[0])
    async def newer():return 'new'
    async def old():
        now[0]+=30
        assert await b.decide('group',newer,owner_attention=False,timeout=1)=='new'
        return 'stale'
    with pytest.raises(module.AttentionDeferred,match='lease_expired_or_replaced'):
        await b.decide('group',old,owner_attention=False,timeout=1)
