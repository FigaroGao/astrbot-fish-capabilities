import json
import pytest
from test_services import BiliFake,BV
from test_astrbot_binding import plugin,Event
from astrbot_plugin_fish_capabilities.services.bilibili import BiliReader
from astrbot_plugin_fish_capabilities.services.bili_memory import BiliMemory
from astrbot_plugin_fish_capabilities.services.bili_duty import BiliDuty

async def test_read_automatically_persists_separate_memory(tmp_path):
    reader=BiliReader(tmp_path/'b.db',BiliFake())
    packet=await reader.read(BV)
    reader.memory.remember(packet,summary='概括字幕观点',reflection='这只是我的推断')
    with reader.connect() as db:db.execute('DELETE FROM readings')
    restored=BiliReader(tmp_path/'b.db',BiliFake())
    found=restored.memory.search('观点')['memories'][0]
    assert found['bvid']==BV and found['reflection']=='这只是我的推断'
    assert found['evidence'] and not found['visual_content_seen']

async def test_cached_read_does_not_duplicate_or_erase_summary(tmp_path):
    r=BiliReader(tmp_path/'b.db',BiliFake());p=await r.read(BV)
    r.memory.remember(p,summary='已记录')
    await r.read(BV)
    data=r.memory.search()
    assert data['total_videos']==1 and data['memories'][0]['summary']=='已记录'

async def test_later_missing_subtitles_preserve_known_evidence(tmp_path):
    r=BiliReader(tmp_path/'b.db',BiliFake());p=await r.read(BV)
    r.memory.remember(dict(p,evidence=[],subtitle_status='unavailable_or_login_required'))
    assert r.memory.search()['memories'][0]['evidence']

async def test_reflection_is_written_to_dedicated_memory(tmp_path):
    r=BiliReader(tmp_path/'b.db',BiliFake());p=await r.read(BV)
    r.reflect(p['reading_id'],'观点仍需进一步验证',[p['evidence'][0]['evidence_id']])
    assert r.memory.search('验证')['memories'][0]['reflection']=='观点仍需进一步验证'

async def test_migration_only_uses_existing_readings(tmp_path):
    r=BiliReader(tmp_path/'b.db',BiliFake());await r.read(BV)
    r.memory.path.unlink()
    restored=BiliReader(tmp_path/'b.db',BiliFake())
    assert restored.memory.search()['total_videos']==1
    assert restored.memory.search('%')['memories']==[]

async def test_manual_scroll_and_memory_tool_owner_private_only(plugin):
    plugin.config.update(enabled=True,bili_enabled=True,owners=['10001'])
    plugin.bili.backend=BiliFake()
    calls=[]
    async def generate(prompt):
        calls.append(prompt)
        return json.dumps({'bvid':BV}) if len(calls)==1 else json.dumps({'recommend':True,'recommendation':'值得阅读','summary':'字幕概要','reflection':'这是阅读后的理解'})
    plugin.bili_generate=generate
    event=Event()
    result=json.loads(await plugin.bili_scroll(event,'天文'))
    assert result['memory_saved'] and len(result['recommendations'])==1 and len(calls)==2
    memory=json.loads(await plugin.bili_memory(event,'概要',5))
    assert memory['memories'][0]['summary']=='字幕概要'
    for outsider in (Event(private=False),Event(sender='other'),Event(admin=False)):
        assert json.loads(await plugin.bili_memory(outsider))['ok'] is False
        assert json.loads(await plugin.bili_scroll(outsider))['ok'] is False
    assert len(calls)==2
