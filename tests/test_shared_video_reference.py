from unittest.mock import AsyncMock
from astrbot_plugin_fish_capabilities.services.private_initiative import Initiative

def test_shared_video_not_latest_browsed_and_survives_restart(tmp_path):
    now=[1000.]
    p=tmp_path/'i.db';i=Initiative(p,AsyncMock(),AsyncMock(),clock=lambda:now[0])
    a=i.offer_video({'bvid':'BV1234567890','reading_id':'first','title':'实际分享的那个'})
    now[0]+=1
    i.offer_video({'bvid':'BVabcdefghij','reading_id':'second','title':'新看但没分享'})
    assert i.shared_videos()==[]
    i.discussed_topic(a)
    got=Initiative(p,AsyncMock(),AsyncMock(),clock=lambda:now[0]).shared_videos()
    assert len(got)==1 and got[0]['bvid']=='BV1234567890'
    assert got[0]['url'].endswith('/BV1234567890')
    now[0]+=8*86400
    assert i.shared_videos()==[]

def test_reserved_and_failed_not_claimed_shared(tmp_path):
    i=Initiative(tmp_path/'i.db',AsyncMock(),AsyncMock(),clock=lambda:1000.)
    a=i.offer_video({'bvid':'BV1234567890','reading_id':'first','title':'pending'})
    with i.db() as db:db.execute("UPDATE topic_states SET state='reserved' WHERE id=?",(a,))
    assert i.shared_videos()==[]
    with i.db() as db:db.execute("UPDATE topic_states SET state='sent' WHERE id=?",(a,))
    assert len(i.shared_videos())==1
