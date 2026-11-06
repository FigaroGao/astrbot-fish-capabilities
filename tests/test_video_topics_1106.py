import json
from test_video_initiative import make_ping

async def test_unrelated_chat_does_not_consume_video_topic(tmp_path):
    p,t,sent,calls=await make_ping(tmp_path)
    ident=p.offer_video({'bvid':'BVreal','reading_id':'r1','title':'鲸鱼','visual_summary':'观察到浮出水面'})
    assert await p.tick()=='sent'
    with p.db() as db:assert db.execute('SELECT state FROM topic_states WHERE id=?',(ident,)).fetchone()[0]=='pending'

async def test_selected_video_consumed_once_and_restart_keeps_other_topics(tmp_path):
    p,t,sent,calls=await make_ping(tmp_path)
    a=p.offer_video({'bvid':'BVone','reading_id':'one','title':'做饭'})
    b=p.offer_video({'bvid':'BVtwo','reading_id':'two','title':'海洋'})
    assert p.offer_video({'bvid':'BVone','reading_id':'new','title':'做饭'})==a
    async def generate(prompt):return json.dumps({'send':True,'message':'我倒觉得这个做法有点意思','selected_topic_id':a})
    p.generate=generate;assert await p.tick()=='sent'
    with p.db() as db:
        assert db.execute('SELECT state FROM topic_states WHERE id=?',(a,)).fetchone()[0]=='sent'
        assert db.execute('SELECT state FROM topic_states WHERE id=?',(b,)).fetchone()[0]=='pending'

async def test_video_survives_two_days_and_hint_is_not_saved(tmp_path):
    p,t,sent,calls=await make_ping(tmp_path)
    p.offer_video({'bvid':'BVreal','reading_id':'r1','title':'鲸鱼'})
    t[0]+=2*86400
    await p.tick(intent_hint='临时想问问游戏')
    assert 'BVreal' in calls[0] and '临时想问问游戏' in calls[0]
    with p.db() as db:assert db.execute('SELECT COUNT(*) FROM topics').fetchone()[0]==1
