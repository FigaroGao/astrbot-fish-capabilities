import json
from types import SimpleNamespace
from unittest.mock import AsyncMock,Mock
import pytest
from test_bili_comments import prepared
from test_services import BV
from astrbot_plugin_fish_capabilities.services.bili_duty import BiliDuty


@pytest.mark.parametrize('self_directed',[False,True])
async def test_owner_arrival_during_selection_prevents_starting_video_read(tmp_path,self_directed):
    reader,packet,comments=await prepared(tmp_path)
    busy=[False]
    async def generate(prompt):
        busy[0]=True;return json.dumps({'bvids':[BV]})
    cfg=dict(comments.settings,bili_scroll_unlimited_enabled=self_directed)
    reader.read=AsyncMock(wraps=reader.read)
    duty=BiliDuty(reader,comments,cfg,generate,AsyncMock())
    duty.brain=SimpleNamespace(available=lambda:not busy[0],work=Mock())
    result=await duty.once('during-choice')
    assert result['state']=='yielded_to_owner' and result['read_count']==0
    reader.read.assert_not_awaited();duty.deliver.assert_not_awaited()
    with reader.connect() as db:assert db.execute('SELECT state FROM bili_jobs').fetchone()[0]=='yielded_to_owner'


async def test_legacy_batch_saves_first_read_but_yields_before_next(tmp_path):
    reader,packet,comments=await prepared(tmp_path);busy=[False]
    other='BV1234567890'
    reader.browse=AsyncMock(return_value={'videos':[{'bvid':BV},{'bvid':other}]})
    original=reader.read
    async def read(*args,**kwargs):
        result=await original(*args,**kwargs);busy[0]=True;return result
    reader.read=AsyncMock(side_effect=read)
    duty=BiliDuty(reader,comments,comments.settings,AsyncMock(return_value=json.dumps({'bvids':[BV,other]})),AsyncMock())
    duty.brain=SimpleNamespace(available=lambda:not busy[0],work=Mock());duty.on_video=Mock()
    result=await duty.once('between-reads')
    assert result['state']=='yielded_to_owner' and result['read_bvids']==[BV]
    assert reader.read.await_count==1 and duty.on_video.call_count==1
    duty.deliver.assert_not_awaited()
