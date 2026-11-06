import json
import pytest
from test_autonomy import make,stamp


@pytest.mark.parametrize('stage',['context','model'])
@pytest.mark.parametrize('boundary',['sleep','deadline'])
async def test_clock_boundary_is_not_reported_as_completed(tmp_path,stage,boundary):
    now=[stamp(3)+59*60 if boundary=='sleep' else stamp()]
    expected='sleeping' if boundary=='sleep' else 'time_window_ended'
    delta=120 if boundary=='sleep' else 900
    worker=make(tmp_path,[{'action':'weather'}],clock=lambda:now[0])
    async def context():
        if stage=='context':now[0]+=delta
        return {}
    async def generate(prompt):
        now[0]+=delta
        return json.dumps({'action':'weather'})
    worker.context=context
    if stage=='model':worker.generate=generate
    result=await worker.tick()
    assert result['state']==expected and not result['steps']
    worker.execute.assert_not_awaited()
    with worker.db() as db:
        assert db.execute('SELECT state FROM cycles').fetchone()[0]==expected
        assert db.execute('SELECT COUNT(*) FROM daily').fetchone()[0]==0
    assert worker.status()['next_decision_at']==now[0]+600
