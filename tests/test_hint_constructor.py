"""Regress the keyword-only Pydantic constructor used by real AstrBot TextPart."""
import sys
import types
from unittest.mock import AsyncMock
import pytest
from pydantic import BaseModel,PrivateAttr
from test_astrbot_binding import plugin,Event


@pytest.fixture
def text_parts(monkeypatch):
    class TextPart(BaseModel):
        type: str='text'
        text: str
        _no_save: bool=PrivateAttr(default=False)
        def mark_as_temp(self):
            self._no_save=True
            return self
    module=types.ModuleType('astrbot.core.agent.message');module.TextPart=TextPart
    monkeypatch.setitem(sys.modules,'astrbot.core.agent.message',module)
    return TextPart


async def test_unified_hint_uses_real_pydantic_constructor_contract(plugin,text_parts):
    plugin.config.update(timetable_enabled=True,timeline_enabled=True,memory_edit_enabled=True)
    req=types.SimpleNamespace(extra_user_content_parts=[])
    await plugin.unified_capability_hints(Event(),req)
    assert len(req.extra_user_content_parts)==1
    part=req.extra_user_content_parts[0]
    assert isinstance(part,text_parts) and part._no_save
    assert 'fish_tasks' in part.text and 'fish_memory_edit' in part.text


async def test_cold_hint_uses_real_pydantic_constructor_and_stays_private(plugin,text_parts):
    plugin.config['cold_archive_enabled']=True
    plugin.cold_scope=AsyncMock(return_value=('test:FriendMessage:owner','persona','cid'))
    plugin.capture_cold_user=AsyncMock()
    req=types.SimpleNamespace(extra_user_content_parts=[])
    await plugin.cold_memory_hints(Event(),req)
    part=req.extra_user_content_parts[0]
    assert isinstance(part,text_parts) and part._no_save and 'fish_recall' in part.text
    plugin.cold_scope=AsyncMock(side_effect=RuntimeError('not an authorized private scope'))
    other=types.SimpleNamespace(extra_user_content_parts=[])
    await plugin.cold_memory_hints(Event(private=False),other)
    assert other.extra_user_content_parts==[]
