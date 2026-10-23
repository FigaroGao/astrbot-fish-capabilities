import types
import pytest

from astrbot_plugin_fish_capabilities.services.commands import CommandGate, install_gate


Plain=type('Plain',(),{})
At=type('At',(),{})
def plain(text):
    value=Plain();value.text=text;return value


class Event:
    def __init__(self,text,owner=False,private=False,mention=False,platform='qq-fish'):
        self.message_str=text;self.owner=owner;self.private=private;self.platform=platform
        self.parts=[plain(text)];self.stopped=False;self.extras={};self.cleared=False
        if mention:
            at=At();at.qq='bot';self.parts.insert(0,at)
    def get_platform_id(self):return self.platform
    def get_sender_id(self):return 'owner' if self.owner else 'other'
    def get_self_id(self):return 'bot'
    def get_messages(self):return self.parts
    def is_private_chat(self):return self.private
    def set_extra(self,k,v):self.extras[k]=v
    def clear_result(self):self.cleared=True
    def stop_event(self):self.stopped=True


@pytest.mark.parametrize('text,private,mention,blocked',[
    ('/help',False,False,True),('/unknown',False,False,True),('  /reset',False,True,True),
    ('#new',False,False,True),('!reset',False,False,True),('／help',False,False,True),
    ('help',True,False,True),('help',False,True,True),('help',False,False,False),
    ('香港天气如何',False,True,False),('为什么 /help 不可用',True,False,False),
    ('https://example.com',False,False,False)])
def test_owner_only_command_detection(text,private,mention,blocked):
    gate=CommandGate(['owner'],['qq-fish'])
    assert gate.blocks(Event(text,private=private,mention=mention),{'wake_prefix':['/']},{'help','reset'}) is blocked
    assert not gate.blocks(Event(text,owner=True,private=private,mention=mention),{'wake_prefix':['/']},{'help','reset'})
    assert not gate.blocks(Event(text,platform='webchat'),{'wake_prefix':['/']},{'help','reset'})


async def test_gate_precedes_parsing_and_is_reversible():
    calls=[]
    class Stage:
        ctx=types.SimpleNamespace(astrbot_config={'wake_prefix':['/']})
        async def process(self,event):calls.append(event.message_str)
    original=Stage.process
    registry=types.SimpleNamespace(star_handlers_map={})
    uninstall=install_gate(Stage,CommandGate(['owner'],['qq-fish']),registry)
    event=Event('/help invalid arguments')
    await Stage().process(event)
    assert event.stopped and event.cleared and event.extras['fish_command_blocked']
    assert calls==[]
    await Stage().process(Event('/help',owner=True))
    assert calls==['/help']
    await Stage().process(Event('香港天气如何'))
    assert calls[-1]=='香港天气如何'
    uninstall();assert Stage.process is original
