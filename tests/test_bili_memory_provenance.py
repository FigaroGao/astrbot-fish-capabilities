from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import json
from astrbot_plugin_fish_capabilities.services.bili_memory import BiliMemory


def packet(stamp,reading,title='示例视频'):
    return {'bvid':'BVsample','reading_id':reading,'fetched_at':stamp,'title':title,
            'url':'https://www.bilibili.com/video/BVsample','evidence':[{'evidence_id':'BVsample:s0','text':'实际内容'}]}


def test_access_or_missing_source_does_not_claim_fresh_evidence(tmp_path):
    now=[1000.];memory=BiliMemory(tmp_path/'m.db',lambda:now[0])
    memory.remember(packet(900.,'r1'),summary='早先的摘要')
    now[0]=2000.;missing=dict(packet(1900.,'r2'),evidence=[])
    memory.remember(missing)
    found=memory.search()['memories'][0]
    assert found['last_read']==2000. and found['source_fetched_at']==900.
    assert found['reading_id']=='r1' and found['evidence']
    assert found['source_retained_reason']=='incoming_evidence_unavailable'
    assert found['annotation_sources']['summary']['reading_id']=='r1'
    assert '不证明来源刚被重新抓取' in memory.search()['instruction']


def test_old_reflection_cannot_replace_newer_packet_and_has_its_own_basis(tmp_path):
    now=[1000.];memory=BiliMemory(tmp_path/'m.db',lambda:now[0])
    old=packet(900.,'r1');memory.remember(old,summary='旧摘要')
    now[0]=2000.;memory.remember(packet(1900.,'r2','后来核验的标题'))
    memory.remember(old,reflection='基于早先阅读的猜想')
    found=memory.search()['memories'][0]
    assert found['reading_id']=='r2' and found['title']=='后来核验的标题'
    assert found['annotation_sources']['summary']['reading_id']=='r1'
    assert found['annotation_sources']['reflection']['reading_id']=='r1'
    assert '_memory_annotation_sources' not in old  # Input packet is not mutated.


def test_legacy_annotation_is_marked_unknown_not_assigned_a_fabricated_source(tmp_path):
    memory=BiliMemory(tmp_path/'m.db',lambda:2000.)
    with memory.connect() as db:
        db.execute('INSERT INTO videos VALUES(?,?,?,?,?,?)',('BVsample',1000.,1000.,json.dumps(packet(900.,'r1')),'旧版摘要',''))
    assert memory.search()['memories'][0]['annotation_sources']['summary']=={'known':False}
    memory.remember(packet(1900.,'r2'))
    found=memory.search()['memories'][0]
    assert found['annotation_sources']['summary']=={'known':False}


def test_concurrent_old_and_new_source_writes_keep_newest_packet(tmp_path):
    memory=BiliMemory(tmp_path/'m.db',lambda:2000.);barrier=Barrier(2)
    def save(value):barrier.wait();memory.remember(value)
    with ThreadPoolExecutor(2) as pool:list(pool.map(save,[packet(900.,'old'),packet(1900.,'new')]))
    assert memory.search()['memories'][0]['reading_id']=='new'
