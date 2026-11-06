import json
from test_video_initiative import make_ping
from astrbot_plugin_fish_capabilities.services.brain import AttentionDeferred

async def test_known_unsent_releases_budget_and_keeps_topic_pending(tmp_path):
    ping,clock,sent,calls=await make_ping(tmp_path)
    ident=ping.offer_video({'bvid':'BVtest','reading_id':'reading','title':'可聊的话题'})
    async def generate(prompt):return json.dumps({'send':True,'message':'想聊的细节','selected_topic_id':ident})
    async def deferred(text):raise AttentionDeferred('another channel won; no transport call')
    ping.generate=generate;ping.deliver=deferred
    assert await ping.tick()=='attention_deferred_no_send'
    with ping.db() as db:
        assert db.execute('SELECT COUNT(*) FROM sends').fetchone()[0]==0
        state,due=db.execute('SELECT state,not_before FROM topic_states WHERE id=?',(ident,)).fetchone()
    assert state=='deferred' and due==clock[0]+120 and not sent

async def test_unknown_network_result_keeps_reservation_and_never_retries(tmp_path):
    ping,clock,sent,calls=await make_ping(tmp_path)
    ident=ping.offer_video({'bvid':'BVtest','reading_id':'reading','title':'可聊的话题'})
    async def generate(prompt):return json.dumps({'send':True,'message':'想聊的细节','selected_topic_id':ident})
    async def unknown(text):raise TimeoutError('may already have been sent')
    ping.generate=generate;ping.deliver=unknown
    assert await ping.tick()=='send_uncertain_no_retry'
    with ping.db() as db:
        assert db.execute('SELECT COUNT(*) FROM sends').fetchone()[0]==1
        assert db.execute('SELECT state FROM topic_states WHERE id=?',(ident,)).fetchone()[0]=='reserved'
