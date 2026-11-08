import json,types
import pytest
from astrbot_plugin_fish_capabilities.services.attribution import reference
from astrbot_plugin_fish_capabilities.services.policy import Ledger,CapabilityError
from test_bili_activity import make

def test_exact_quote_not_last_answer():
    p=type('Plain',(),{})();p.text='这是之前那一条实际说过的话'
    q=type('Reply',(),{})();q.id='old';q.sender_id='bot';q.chain=[p];q.message_str='fallback'
    e=types.SimpleNamespace(get_sender_id=lambda:'owner',get_self_id=lambda:'bot',get_messages=lambda:[q],is_private_chat=lambda:True)
    data=json.loads(reference(e,['owner']).split('\n')[1])
    assert data['quoted_messages'][0]['text']==p.text
    assert data['quoted_messages'][0]['text_available']
    q.chain=[];q.message_str=''
    assert not json.loads(reference(e,['owner']).split('\n')[1])['quoted_messages'][0]['text_available']

def test_browse_rephrase_and_media_budgets_separate(tmp_path):
    l=Ledger(tmp_path/'ledger.db')
    l.reserve('owner','image','turn',cooldown=0,hourly=12,now=100)
    for _ in range(3):l.reserve('owner:bili','browse','turn:browse',cooldown=0,hourly=12,per_turn_limit=3,now=100)
    with pytest.raises(CapabilityError,match='候选搜索'):l.reserve('owner:bili','browse','turn:browse',cooldown=0,hourly=12,per_turn_limit=3,now=100)
    with pytest.raises(CapabilityError):l.reserve('owner','image','turn',cooldown=0,hourly=12,now=100)
    with pytest.raises(CapabilityError):l.reserve('owner','image','new',cooldown=0,hourly=12,per_turn_limit=3,now=100)

@pytest.mark.asyncio
async def test_video_activity_without_private_context(tmp_path):
    a,b,r,g,n,t,c=make(tmp_path)
    c.clear();c['private_activity_timeline']=[{'kind':'bili_read','at':t[0],'summary':'实际已读的公开视频','details':{}}]
    await a.think()
    g.assert_awaited_once()
    assert 'at' not in c

@pytest.mark.asyncio
async def test_quarantined_or_future_activity_not_fresh(tmp_path):
    a,b,r,g,n,t,c=make(tmp_path)
    c.clear();c['private_activity_timeline']=[{'kind':'bili_read','at':t[0],'details':{'cold_derived':True}}, {'kind':'bili_read','at':t[0]+10,'details':{}}, {'kind':'qq','at':t[0]}]
    assert (await a.think())['state']=='no_new_context'
    g.assert_not_awaited()
