import asyncio
from types import SimpleNamespace
import pytest
from astrbot_plugin_fish_capabilities.services.photo_caption import PhotoCaption

class Event:
    def __init__(self,kinds,text='',raw=None,sender='owner'):
        self.unified_msg_origin='private:'+sender
        self.get_sender_id=lambda:sender
        self.parts=[type(k,(),{})() for k in kinds]
        self.get_messages=lambda:self.parts
        self.get_message_str=lambda:text
        self.message_obj=SimpleNamespace(raw_message={'message':raw or []})
        self.stopped=False
    def stop_event(self):self.stopped=True

async def test_album_and_caption_proceed_as_one():
    gate=PhotoCaption();first=Event(['Image']);second=Event(['Image']);caption=Event(['Plain'],'看看右边')
    task=asyncio.create_task(gate.observe(first,2));await asyncio.sleep(0)
    await gate.observe(second,2);await gate.observe(caption,2);await task
    assert first.stopped and second.stopped and not caption.stopped
    assert [type(p).__name__ for p in caption.parts]==['Image','Image','Plain']
    assert not gate.pending

async def test_timeout_after_unrelated_sender_or_command():
    gate=PhotoCaption();photo=Event(['Image'])
    task=asyncio.create_task(gate.observe(photo,.03));await asyncio.sleep(0)
    for e in [Event(['Plain'],'看看',sender='other'),Event(['Plain'],'/状态')]:
        await gate.observe(e,2);assert len(e.parts)==1
    await task
    assert not photo.stopped and not gate.pending

@pytest.mark.parametrize('e',[Event(['Image','Plain'],'这是什么'),Event(['Face']),Event(['Image'],raw=[{'type':'mface'}]),Event(['Image'],raw=[{'type':'image','data':{'sub_type':1}}])])
async def test_immediate_paths(e):
    gate=PhotoCaption();await asyncio.wait_for(gate.observe(e,5),.1)
    assert not gate.pending and not e.stopped
