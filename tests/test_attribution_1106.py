import types,json
from astrbot_plugin_fish_capabilities.services.attribution import reference
from astrbot_plugin_fish_capabilities.services.activity_timeline import ActivityTimeline
from astrbot_plugin_fish_capabilities.services.brain import Brain
from astrbot_plugin_fish_capabilities.services.context_budget import slim

def test_reply_speaker_is_distinct_from_current_user_and_bot():
    Reply=type('Reply',(),{})
    reply=Reply();reply.sender_id='another';reply.id='message'
    e=types.SimpleNamespace(get_sender_id=lambda:'member',get_self_id=lambda:'bot',get_messages=lambda:[reply],is_private_chat=lambda:False)
    text=reference(e,['owner']);data=json.loads(text.split('\n')[1])
    assert data['current_speaker_id']=='member' and data['assistant_id']=='bot'
    assert not data['current_speaker_is_owner'] and data['quoted_messages'][0]['sender_id']=='another'
    assert '图片' in text and 'role=assistant' in text

def test_background_tasks_do_not_hide_video_activity(tmp_path):
    t=ActivityTimeline(tmp_path/'t.db',lambda:1000.)
    t.add('bili_read','video','读了视频')
    for i in range(20):t.add('task',str(i),'定时任务')
    assert [x['kind'] for x in t.search('',6)['events']]==['bili_read']
    assert len(t.search('定时任务',6)['events'])==6

def test_private_ping_does_not_silence_group_but_owner_and_mute_do(tmp_path):
    now=[1000.];b=Brain(tmp_path/'b.db',lambda:now[0])
    lease=b.claim('qq','hello');b.finish(lease,True)
    assert not b.available() and b.group_available()
    b.observe('owner');assert not b.group_available()
    now[0]+=121;b.mute(10);assert not b.group_available()

def test_completed_last_answer_keeps_spoken_text_not_old_reasoning():
    rows=[{'role':'user','content':'hello'}, {'role':'assistant','reasoning_content':'old internal draft','content':[{'type':'think','think':'old draft'},{'type':'text','text':'spoken reply'}]}]
    clean=slim(rows)
    assert clean[-1]['content']==[{'type':'text','text':'spoken reply'}]
    assert 'reasoning_content' not in clean[-1] and 'reasoning_content' in rows[-1]

def test_active_tool_protocol_keeps_required_reasoning():
    rows=[{'role':'user','content':'query'},{'role':'assistant','tool_calls':[{'id':'call1'}],'reasoning_content':'active protocol'},{'role':'tool','tool_call_id':'call1','content':'result'}]
    assert slim(rows)[1]['reasoning_content']=='active protocol'
