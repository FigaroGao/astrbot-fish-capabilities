import asyncio
from unittest.mock import AsyncMock
import pytest
from test_services import BiliFake
from astrbot_plugin_fish_capabilities.services.bilibili import BiliReader
@pytest.mark.asyncio
async def test_audio_result_and_failure(tmp_path):
 r=BiliReader(tmp_path/'b.db',BiliFake())
 r.audio_reader=AsyncMock(return_value={'audio_heard':True,'audio_segments':[{'start':0,'end':10,'description':'弦乐'}],'audio_summary':'弦乐'})
 p=await r.read('BV1234567890',listen=True)
 assert p['audio_heard'] and p['audio_segments'][0]['end']==10
 r.audio_reader.assert_awaited_once()
 await r.read('BV1234567890',listen=True);r.audio_reader.assert_awaited_once()

@pytest.mark.asyncio
async def test_audio_unavailable_keeps_video_and_cancel_propagates(tmp_path):
 r=BiliReader(tmp_path/'failed.db',BiliFake());r.audio_reader=AsyncMock(side_effect=TimeoutError())
 p=await r.read('BV1234567890',listen=True);assert not p['audio_heard'] and p['audio_status']=='unavailable'
 r=BiliReader(tmp_path/'cancel.db',BiliFake());r.audio_reader=AsyncMock(side_effect=asyncio.CancelledError())
 with pytest.raises(asyncio.CancelledError):await r.read('BV1234567890',listen=True)

@pytest.mark.asyncio
async def test_default_does_not_listen(tmp_path):
 r=BiliReader(tmp_path/'optional.db',BiliFake());r.audio_reader=AsyncMock(return_value={'audio_heard':True})
 p=await r.read('BV1234567890');assert not p['audio_heard']
 r.audio_reader.assert_not_awaited()
 p=await r.read('BV1234567890',listen=True);assert p['audio_heard']
 r.audio_reader.assert_awaited_once()
