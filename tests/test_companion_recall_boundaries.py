from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from astrbot_plugin_fish_capabilities.services.companion_learning import CompanionLearning
from astrbot_plugin_fish_capabilities.services.policy import CapabilityError


def test_pending_notes_cannot_hide_approved_reference_before_limit(tmp_path):
    clock=[1000.];store=CompanionLearning(tmp_path/'notes.db',lambda:clock[0])
    original=store.save('owner','style_positive','视频 分享','分享一个具体细节',{'kind':'owner_review'},approved=True)
    for i in range(105):
        clock[0]+=1;store.save('owner','observation','其他','待审材料'+str(i),{'kind':'owner_statement'})
    assert [r['id'] for r in store.list('owner',include_pending=False,limit=1)]==[original['id']]
    assert [r['id'] for r in store.recall('owner','视频分享',kinds={'style_positive'})]==[original['id']]
    assert not store.recall('group','视频分享')


def test_new_approved_preferences_do_not_crowd_out_older_style_hint(tmp_path):
    clock=[1000.];store=CompanionLearning(tmp_path/'notes.db',lambda:clock[0])
    store.save('owner','style_negative','视频 分享','不交长篇观看总结',{'kind':'owner_review'},approved=True)
    for i in range(105):
        clock[0]+=1;store.save('owner','preference','视频','偏好材料'+str(i),{'kind':'owner_statement'},approved=True)
    assert '不交长篇观看总结' in store.style_hint('owner','视频分享')


def test_concurrent_reviews_with_same_version_have_one_winner(tmp_path):
    store=CompanionLearning(tmp_path/'notes.db')
    item=store.save('owner','observation','课程','推测课程比较忙',{'kind':'owner_statement'})
    barrier=Barrier(2)
    def review(state):
        barrier.wait()
        try:store.review('owner',item['id'],state,1);return True
        except CapabilityError:return False
    with ThreadPoolExecutor(2) as pool:result=list(pool.map(review,['approved','rejected']))
    assert sum(result)==1
    with store.db() as db:
        assert db.execute('SELECT revision FROM notes').fetchone()[0]==2
        assert db.execute('SELECT COUNT(*) FROM revisions').fetchone()[0]==1
