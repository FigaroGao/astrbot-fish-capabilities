import time
import pytest
from astrbot_plugin_fish_capabilities.services.bilibili import BiliReader
from astrbot_plugin_fish_capabilities.services.policy import CapabilityError
from test_services import BiliFake,BV

async def test_zero_budget_allows_reads_and_notes_without_erasing_usage(tmp_path):
    reader=BiliReader(tmp_path/'b.db',BiliFake(),daily_reads=0,daily_notes=0)
    with reader.connect() as db:
        db.executemany('INSERT INTO attempts VALUES(?)',[(time.time(),)]*20)
    packet=await reader.read(BV)
    for _ in range(10):
        assert reader.reflect(packet['reading_id'],'有来源的札记',[packet['evidence'][0]['evidence_id']])['saved']
    with reader.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0]==21
    with pytest.raises(CapabilityError):reader.reflect(packet['reading_id'],'无来源',['invented'])

async def test_positive_note_budget_still_enforced(tmp_path):
    reader=BiliReader(tmp_path/'b.db',BiliFake(),daily_notes=1)
    packet=await reader.read(BV)
    ids=[packet['evidence'][0]['evidence_id']]
    reader.reflect(packet['reading_id'],'札记',ids)
    with pytest.raises(CapabilityError,match='预算'):reader.reflect(packet['reading_id'],'另一条',ids)
