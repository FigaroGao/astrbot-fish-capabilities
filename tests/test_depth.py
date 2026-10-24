import sys,types
from unittest.mock import AsyncMock
from test_astrbot_binding import plugin,Event


async def test_disabled_and_unauthorized_contexts_are_untouched(plugin):
    req=types.SimpleNamespace(prompt='原文',extra_user_content_parts=[])
    await plugin.support_conversation_depth(Event(),req)
    plugin.config['conversation_depth_enabled']=True
    await plugin.support_conversation_depth(Event(sender='other',admin=False),req)
    plugin.config['allowed_group_sessions']=[]
    await plugin.support_conversation_depth(Event(private=False),req)
    assert req.extra_user_content_parts==[] and req.prompt=='原文'


async def test_authorized_guidance_is_temporary_scoped_and_needs_no_extra_inference(plugin,monkeypatch):
    class TextPart:
        def __init__(self,text):self.text=text;self._no_save=False
        def mark_as_temp(self):self._no_save=True;return self
    module=types.ModuleType('astrbot.core.agent.message');module.TextPart=TextPart
    monkeypatch.setitem(sys.modules,module.__name__,module)
    plugin.config['conversation_depth_enabled']=True
    plugin.bounded_generate=AsyncMock()
    private=types.SimpleNamespace(prompt='原文',extra_user_content_parts=[])
    group=types.SimpleNamespace(prompt='群原文',extra_user_content_parts=[])
    await plugin.support_conversation_depth(Event(),private)
    await plugin.support_conversation_depth(Event(private=False),group)
    assert private.prompt=='原文' and group.prompt=='群原文'
    assert all(r.extra_user_content_parts[0]._no_save for r in [private,group])
    assert '当前是主人私聊' in private.extra_user_content_parts[0].text
    assert '不引用或暗示任何私聊资料' in group.extra_user_content_parts[0].text
    assert '当前是主人私聊' not in group.extra_user_content_parts[0].text
    plugin.bounded_generate.assert_not_awaited()
