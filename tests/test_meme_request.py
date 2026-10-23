from types import SimpleNamespace as NS
import pytest
from astrbot_plugin_fish_capabilities.services.meme_request import explicit_meme_request
from astrbot_plugin_fish_capabilities.services.policy import Ledger,CapabilityError


def event(text,targets=(),private=False):
    Plain=type('Plain',(),{})
    p=Plain();p.text=text
    return NS(get_messages=lambda:[p,*targets],get_self_id=lambda:'bot',is_private_chat=lambda:private)


def at(target):return type('At',(),{'qq':target})()
def quote(target,text=''):return type('Reply',(),{'sender_id':target,'message_str':text})()


@pytest.mark.parametrize('text,parts,expected',[
    ('发个表情包',[at('bot')],True),('再来一张',[quote('bot')],True),
    ('小鲸给我来个表情包',[],True),('大肥鱼，发张贴图',[],True),
    ('别发表情包',[at('bot')],False),('不用给我发表情',[at('bot')],False),
    ('给我发表情包',[at('other')],False),('小鲸发个表情包',[quote('other')],False),
    ('有人说让你发表情包',[at('bot')],False),('你好',[quote('bot','给我发表情包')],False),
    ('发个表情包',[],False),('你觉得今天怎么样',[at('bot')],False),
])
def test_only_current_explicit_request(text,parts,expected):
    assert explicit_meme_request(event(text,parts)) is expected


def test_request_bypasses_gap_and_cooldown_but_resets_and_keeps_hard_limits(tmp_path):
    ledger=Ledger(tmp_path/'budget.db')
    ledger.reserve('g','image','first',cooldown=180,hourly=3,min_reply_gap=3,now=100)
    ledger.reserve('g','image','requested',cooldown=180,hourly=3,min_reply_gap=3,now=101,requested=True)
    with pytest.raises(CapabilityError):
        ledger.reserve('g','image','auto',cooldown=180,hourly=3,min_reply_gap=3,now=102)
    with pytest.raises(CapabilityError,match='本轮'):
        ledger.reserve('g','image','requested',cooldown=180,hourly=3,now=102,requested=True)
    ledger.reserve('g','image','third',cooldown=180,hourly=3,now=103,requested=True)
    with pytest.raises(CapabilityError,match='本小时'):
        ledger.reserve('g','image','fourth',cooldown=180,hourly=3,now=104,requested=True)
    with pytest.raises(CapabilityError):
        ledger.reserve('g','record','voice',cooldown=180,hourly=3,now=104,requested=True)
