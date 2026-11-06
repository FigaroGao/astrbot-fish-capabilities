"""Exercise real adapters with mock transports, never actual public sends."""
import types
import pytest
from test_bili_comments import prepared
from astrbot_plugin_fish_capabilities.services.brain import Brain,AttentionDeferred
from astrbot_plugin_fish_capabilities.services.brain_context import BrainContext
from astrbot_plugin_fish_capabilities.services.policy import CapabilityError
from test_astrbot_binding import plugin,Event

async def test_guarded_bili_deferral_does_not_pause_account(tmp_path):
    reader,packet,writer=await prepared(tmp_path)
    brain=Brain(tmp_path/'brain.db');brain.guard_backend(writer.backend,'send')
    brain.mute(60)
    evidence=[packet['evidence'][0]['evidence_id']]
    with pytest.raises(AttentionDeferred):await writer.post(packet['reading_id'],'这个观点不错',evidence)
    assert writer.backend.calls==0 and not writer.status()['paused']
    brain.mute(0)
    assert (await writer.post(packet['reading_id'],'这个观点不错',evidence))['submitted']
    assert writer.backend.calls==1

async def test_guard_preserves_existing_permissions(tmp_path):
    _,packet,writer=await prepared(tmp_path)
    brain=Brain(tmp_path/'brain.db');brain.guard_backend(writer.backend,'send')
    writer.settings['bili_account_id']='wrong'
    with pytest.raises(CapabilityError):await writer.post(packet['reading_id'],'不错',[packet['evidence'][0]['evidence_id']])
    assert writer.backend.calls==0

async def test_context_uses_single_identity_but_review_gets_no_persona(tmp_path):
    cap=types.SimpleNamespace(config={'companionship_enabled':True},brain=Brain(tmp_path/'brain.db'))
    builder=BrainContext(cap)
    async def identity():return 'existing persona identity'
    builder.identity=identity
    for kind in ('private_initiative','autonomy_decision','screenmate_intent','bili_reply_draft'):
        text=await builder.compose(kind,'specialist task')
        assert text.count('existing persona identity')==1 and 'specialist task' in text
    assert await builder.compose('bili_public_review','independent review')=='independent review'

async def test_attention_tool_is_owner_private_and_preserves_chat(plugin):
    plugin.config.update(enabled=True,companionship_enabled=True)
    event=Event(private=False)
    result=await plugin.attention_tool(event,'mute',500)
    assert 'muted_until' not in plugin.brain.snapshot()['attention']
    await plugin.attention_tool(Event(),'mute',500)
    assert not plugin.brain.available()
    await plugin.attention_tool(Event(),'resume')
    assert plugin.brain.available()

async def test_reading_yields_with_progress_without_public_or_private_send(tmp_path):
    import json
    from astrbot_plugin_fish_capabilities.services.bili_duty import BiliDuty
    from test_services import BV
    reader,packet,writer=await prepared(tmp_path)
    brain=Brain(tmp_path/'brain.db')
    original=reader.read
    async def read(*args,**kwargs):
        result=await original(*args,**kwargs);brain.observe('owner');return result
    reader.read=read
    async def generate(prompt):return json.dumps({'bvids':[BV],'frame_count':9})
    async def forbidden(*args):raise AssertionError('must not send')
    duty=BiliDuty(reader,writer,dict(bili_scroll_unlimited_enabled=True),generate,forbidden)
    duty.brain=brain
    result=await duty.once('background-test')
    assert result['state']=='yielded_to_owner' and result['read_bvids']==[BV]
    progress=json.loads(brain.recall_work('bili_progress'))
    assert progress['readings'] and writer.backend.calls==0
