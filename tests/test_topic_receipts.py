import json
from test_bili_comments import prepared
from test_services import BV
from astrbot_plugin_fish_capabilities.services.bili_duty import BiliDuty

async def test_saved_topic_is_not_reported_as_delivered_recommendation(tmp_path):
    reader,p,w=await prepared(tmp_path);w.settings['bili_comment_enabled']=False
    calls=[];topics=[]
    async def generate(prompt):
        calls.append(prompt)
        return json.dumps({'bvid':BV}) if len(calls)==1 else json.dumps({'bvid':BV,'recommend':True,'recommendation':'有个细节想聊'})
    async def deliver(text):raise AssertionError('candidate must not auto-send')
    duty=BiliDuty(reader,w,w.settings,generate,deliver);duty.on_video=lambda *args:topics.append(args)
    result=await duty.once('saved')
    assert result['state']=='topic_saved' and topics

async def test_final_draft_cannot_switch_even_single_video_target(tmp_path):
    reader,p,w=await prepared(tmp_path)
    calls=[]
    async def generate(prompt):
        calls.append(prompt)
        return json.dumps({'bvid':BV}) if len(calls)==1 else json.dumps({'bvid':'not-read','recommend':True,'recommendation':'invented','comment':'invented'})
    async def deliver(text):raise AssertionError('invalid target must not send')
    result=await BiliDuty(reader,w,w.settings,generate,deliver).once('bad-target')
    assert result['state']=='read_without_recommendation' and w.backend.calls==0
