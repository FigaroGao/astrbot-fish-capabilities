from astrbot_plugin_fish_capabilities.services.companion_learning import CompanionLearning


def test_expired_duplicate_does_not_pretend_to_refresh_or_reapprove(tmp_path):
    now=[1000.];store=CompanionLearning(tmp_path/'notes.db',lambda:now[0])
    note=store.save('owner','observation','上课','推测这周课程较忙',{'kind':'owner_statement'},approved=True)
    now[0]+=8*86400
    again=store.save('owner','observation','上课','推测这周课程较忙',{'kind':'owner_statement'},approved=True)
    assert again['id']==note['id'] and again['expired'] and not again['effective']
    assert again['requires_revision_update'] and not store.recall('owner','上课')
    with store.db() as db:
        assert db.execute('SELECT COUNT(*) FROM notes').fetchone()[0]==1
        assert db.execute('SELECT stamp FROM notes').fetchone()[0]==1000.


def test_archived_style_requires_explicit_versioned_update(tmp_path):
    store=CompanionLearning(tmp_path/'notes.db')
    note=store.save('owner','style_negative','闲聊','别机械列清单',{'kind':'owner_review'},approved=True)
    archived=store.review('owner',note['id'],'archived',1)
    again=store.save('owner','style_negative','闲聊','别机械列清单',{'kind':'owner_review'},approved=True)
    assert not again['effective'] and again['requires_revision_update']
    assert not store.style_hint('owner','闲聊')
    store.save('owner','style_negative','闲聊','别机械列清单',{'kind':'owner_review'},approved=True,note_id=note['id'],revision=archived['revision'])
    assert '别机械列清单' in store.style_hint('owner','闲聊')
