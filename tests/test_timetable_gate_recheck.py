"""A second instance can revoke a task while its async intent gate waits."""
import asyncio
from unittest.mock import AsyncMock
import pytest
from test_unified_capabilities import board
from astrbot_plugin_fish_capabilities.services.timetable import Timetable


@pytest.mark.parametrize('operation',['pause','cancel','revise'])
@pytest.mark.parametrize('decision',['run','defer'])
async def test_external_change_during_gate_prevents_old_action_or_deferral(tmp_path,operation,decision):
    timetable,_,clock=board(tmp_path)
    called=AsyncMock();entered=asyncio.Event();release=asyncio.Event()
    async def gate(action):
        entered.set();await release.wait()
        return {'decision':decision,'delay_seconds':60}
    timetable.actions['bili_scroll']=called;timetable.gate=gate
    ident=timetable.put('browse','bili_scroll','* * * * *')['task_id']
    await timetable.tick();await asyncio.wait_for(entered.wait(),2)
    # This instance has no reference to the first instance's asyncio.Task.
    other=Timetable(timetable.path,timetable.actions,clock=lambda:clock[0])
    if operation=='revise':other.put('new browse','bili_scroll','0 12 * * *',task_id=ident)
    else:other.control(ident,operation)
    release.set();await timetable.drain()
    called.assert_not_awaited()
    with timetable.db() as db:
        assert db.execute('SELECT COUNT(*) FROM deferrals').fetchone()[0]==0
        assert db.execute('SELECT state FROM executions').fetchone()[0]=='cancelled'
