from types import SimpleNamespace as NS
from unittest.mock import Mock
import pytest
from test_astrbot_binding import plugin,Event
from astrbot_plugin_fish_capabilities.services.group_quiet import install_send_guard


async def test_guard_observer_only_runs_after_success_not_suppression_or_error():
    quiet=NS(suppress=lambda event:event.suppressed)
    observed=[]
    class Message:
        suppressed=False;fail=False
        async def send(self,value):
            if self.fail:raise TimeoutError()
            return 'adapter accepted'
        def clear_result(self):pass
        def stop_event(self):pass
    undo=install_send_guard(Message,quiet,after_send=lambda e,v:observed.append(v))
    try:
        e=Message();assert await e.send('first')=='adapter accepted'
        e.suppressed=True;await e.send('muted');e.suppressed=False;e.fail=True
        with pytest.raises(TimeoutError):await e.send('unknown')
        assert observed==['first']
    finally:undo()


async def test_observer_failure_does_not_change_successful_transport_result():
    class Message:
        async def send(self,value):return 'accepted once'
    undo=install_send_guard(Message,NS(suppress=lambda e:False),after_send=Mock(side_effect=ValueError()))
    try:assert await Message().send('text')=='accepted once'
    finally:undo()


async def test_draft_is_not_inserted_in_initiative_chat_and_accepted_segments_are(plugin,monkeypatch):
    from astrbot.api import message_components as Comp
    class Plain:pass
    monkeypatch.setattr(Comp,'Plain',Plain,raising=False)
    plugin.config.update(enabled=True,command_platform_ids=['qq_test'],timeline_enabled=True)
    plugin.private_ping=NS(observe=Mock());event=Event()
    plugin.intent.enabled=lambda e:False
    await plugin.note_group_answer(event,NS(completion_text='未发送的草稿'))
    plugin.private_ping.observe.assert_not_called()
    # Real Plain type in production; stub instances carry equivalent fields.
    first=Comp.Plain();first.text='实际第一段'
    second=Comp.Plain();second.text='实际第二段'
    plugin.capture_private_delivery(event,NS(chain=[first]))
    plugin.capture_private_delivery(event,NS(chain=[second]))
    await plugin.note_reply_turn(event)
    plugin.private_ping.observe.assert_called_once_with('实际第一段\n实际第二段','assistant')
    await plugin.note_reply_turn(event)
    assert plugin.private_ping.observe.call_count==1


async def test_group_or_other_user_delivery_does_not_enter_owner_private_chat(plugin,monkeypatch):
    from astrbot.api import message_components as Comp
    class Plain:pass
    monkeypatch.setattr(Comp,'Plain',Plain,raising=False)
    plugin.private_ping=NS(observe=Mock())
    text=Comp.Plain();text.text='其他会话'
    for event in (Event(private=False),Event(sender='other')):
        plugin.capture_private_delivery(event,NS(chain=[text]))
        assert not event.get_extra('fish_private_delivery_text')
