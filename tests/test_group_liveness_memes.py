from types import SimpleNamespace as NS
import json
import pytest
from test_intent_runtime import Event,runtime,Gcp,consume
from test_astrbot_binding import plugin
from test_services import make_library
from astrbot_plugin_fish_capabilities.services.meme_opportunity import opportunity


async def test_ordinary_followup_during_judgment_merges_into_one_live_batch(runtime):
    runtime.cap.config['intent_live_batch_enabled']=True
    async def judge(*args):
        runtime.observe(Event('哈哈这个也太有意思了'))
        return True
    runtime.judge=judge;g=Gcp();event=Event('今天看到鲸鱼了')
    assert await consume(runtime,g,event)==['one whole response']
    assert g.calls==1 and event.get_extra('fish_intent_group_snapshot')[-1]['text']=='哈哈这个也太有意思了'


@pytest.mark.parametrize('text',['已经解决了','先别说，换个话题','不用回了'])
async def test_closed_context_still_cancels_live_batch(runtime,text):
    runtime.cap.config['intent_live_batch_enabled']=True
    async def judge(*args):runtime.observe(Event(text));return True
    runtime.judge=judge;g=Gcp()
    assert await consume(runtime,g,Event())==[] and g.calls==0


async def test_continuous_ordinary_chat_does_not_wait_forever(runtime):
    runtime.cap.config.update(intent_live_batch_enabled=True,intent_quiet_seconds=6)
    async def sleep(seconds):
        runtime.test_now[0]+=seconds
        runtime.observe(Event('又一条普通跟帖'))
    runtime.sleep=sleep;g=Gcp()
    assert await consume(runtime,g,Event()) and runtime.test_now[0]<=1013
    assert g.calls==1


def test_local_meme_candidates_do_not_queue_or_charge_and_respect_no_image_request(plugin):
    make_library(plugin.root/'memes')
    hint=opportunity(plugin,'private','哈哈，好开心',now=1000)
    assert 'fish_meme' in hint and '不是发送要求' in hint
    assert not plugin.media.pending
    with plugin.ledger.connect() as db:assert db.execute('SELECT COUNT(*) FROM reservations').fetchone()[0]==0
    assert opportunity(plugin,'private','哈哈但不要发表情包',now=1000) is None
    assert opportunity(plugin,'private','详细解释一下代码为什么报错',now=1000) is None


def test_hourly_media_limit_still_stops_candidate_offer(plugin):
    make_library(plugin.root/'memes');plugin.config['media_hourly_limit']=1
    plugin.ledger.reserve('private','image','turn',cooldown=0,hourly=1,now=1000)
    assert opportunity(plugin,'private','哈哈开心',now=1001) is None
