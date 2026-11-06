import asyncio,json
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from test_autonomy import make,stamp


@pytest.mark.parametrize('waiting_stage',['context','model'])
async def test_old_cycle_cannot_execute_or_release_replacement_lease(tmp_path,waiting_stage):
    now=[stamp()];old_entered=asyncio.Event();old_release=asyncio.Event()
    new_entered=asyncio.Event();new_release=asyncio.Event()
    old=make(tmp_path,[{'action':'weather'}],clock=lambda:now[0])
    async def blocked():
        old_entered.set();await old_release.wait()
        return {} if waiting_stage=='context' else json.dumps({'action':'weather'})
    if waiting_stage=='context':old.context=blocked
    else:old.generate=lambda prompt:blocked()
    async def execute(*args):new_entered.set();await new_release.wait();return {'state':'done'}
    new=make(tmp_path,[{'action':'review_notes'}],execute,lambda:now[0])
    brain=SimpleNamespace(available=lambda:True,work=Mock());old.brain=new.brain=brain
    first=asyncio.create_task(old.tick());await old_entered.wait();now[0]+=1801
    second=asyncio.create_task(new.tick());await new_entered.wait()
    old_release.set();assert (await first)['state']=='lease_lost'
    old.execute.assert_not_awaited()
    assert new.status()['running_lease_until']>now[0]
    assert brain.work.call_args.args==('autonomy','running:review_notes')
    with new.db() as db:
        assert db.execute('SELECT v FROM state WHERE k="finished"').fetchone() is None
        assert db.execute('SELECT COUNT(*) FROM daily').fetchone()[0]==0
    third=make(tmp_path,[],clock=lambda:now[0]);assert (await third.tick())['state']=='running'
    new_release.set();assert (await second)['state']=='completed'
    assert new.status()['next_decision_at']==now[0]+600


async def test_expired_legacy_cycle_is_classified_without_losing_saved_steps(tmp_path):
    now=stamp();worker=make(tmp_path,[{'action':'quiet'}],clock=lambda:now)
    saved='[{"action":"recall","state":"done"}]'
    with worker.db() as db:
        db.execute('INSERT INTO cycles(start,state,steps) VALUES(?,?,?)',(now-1801,'running',saved))
        db.execute('INSERT INTO state VALUES(?,?)',('lease',now-1))
    assert (await worker.tick())['state']=='completed'
    with worker.db() as db:
        assert db.execute('SELECT state,steps FROM cycles ORDER BY id LIMIT 1').fetchone()==('lease_expired',saved)
