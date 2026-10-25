import types
from unittest.mock import AsyncMock
from astrbot_plugin_fish_capabilities.services.group_quiet import GroupQuiet,install_send_guard
from test_astrbot_binding import plugin,Event


class QuietEvent(Event):
    unified_msg_origin='qq_test:GroupMessage:77777'
    def __init__(self, text='/闭嘴', **kw):
        super().__init__(private=False,**kw);self.text=text;self.stopped=False;self.sent=[]
    def get_messages(self):
        Plain=type('Plain',(),{})
        part=Plain();part.text=self.text;return [part]
    def stop_event(self):self.stopped=True
    def clear_result(self):self.result=None
    def plain_result(self,text):return text
    async def send(self,result):self.sent.append(result)


async def test_owner_mute_resume_and_others_cannot_unmute(plugin):
    owner=QuietEvent()
    assert await plugin.group_quiet_before_wake(owner)
    assert plugin.group_quiet.muted(owner.unified_msg_origin) and len(owner.sent)==1
    other=QuietEvent('/开口',sender='other',admin=False)
    assert await plugin.group_quiet_before_wake(other)
    assert plugin.group_quiet.muted(owner.unified_msg_origin) and not other.sent
    resume=QuietEvent('/开口')
    assert await plugin.group_quiet_before_wake(resume)
    assert not plugin.group_quiet.muted(owner.unified_msg_origin)


async def test_window_expiry_and_old_queue_stays_suppressed(tmp_path):
    now=[1000];q=GroupQuiet(tmp_path/'quiet.json',clock=lambda:now[0])
    old=QuietEvent('旧回答');q.mark(old);q.set(old.unified_msg_origin,120)
    assert q.suppress(old)
    now[0]+=121
    assert not q.muted(old.unified_msg_origin) and q.suppress(old)
    fresh=QuietEvent('新消息');q.mark(fresh);assert not q.suppress(fresh)
    assert GroupQuiet(q.path,clock=lambda:now[0]).state==q.state


async def test_send_guard_stops_remaining_segments_but_not_private(tmp_path):
    q=GroupQuiet(tmp_path/'quiet.json')
    class E(QuietEvent):pass
    undo=install_send_guard(E,q)
    try:
        e=E();q.mark(e);await e.send('第一段');q.set(e.unified_msg_origin,120);await e.send('第二段')
        assert e.sent==['第一段'] and e.stopped
        private=E();private.private=True;await private.send('私聊照常');assert private.sent==['私聊照常']
    finally:undo()


async def test_only_exact_current_message_command(plugin):
    event=QuietEvent('他说了/闭嘴，但我没叫你闭嘴')
    assert not await plugin.group_quiet_before_wake(event)
    assert not plugin.group_quiet.state


async def test_muted_messages_blocked_before_llm(plugin):
    q=plugin.group_quiet
    e=QuietEvent('普通消息');q.set(e.unified_msg_origin,120)
    assert await plugin.group_quiet_before_wake(e)
    assert e.stopped and not e.sent


async def test_owner_before_waking_role_assignment_uses_stage_admin_config(plugin):
    event=QuietEvent(admin=False)
    assert await plugin.group_quiet_before_wake(event,{'admins_id':['10001']})
    assert plugin.group_quiet.muted(event.unified_msg_origin) and event.sent


async def test_forged_admin_role_not_enough_before_wake(plugin):
    event=QuietEvent(admin=True)
    assert await plugin.group_quiet_before_wake(event,{'admins_id':['different']})
    assert not plugin.group_quiet.state and not event.sent
