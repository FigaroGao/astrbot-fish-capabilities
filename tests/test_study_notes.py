import pytest
from unittest.mock import AsyncMock
from test_astrbot_binding import plugin
from astrbot_plugin_fish_capabilities.services.policy import CapabilityError

async def test_video_to_search_to_correction(plugin,monkeypatch):
    scope='test:FriendMessage:owner'
    plugin.config.update(owner_notes_enabled=True,bili_private_session=scope)
    question='显存带宽如何影响推理？'
    packet={'title':'带宽','bvid':'BVtest','reading_id':'read1','evidence':[{'evidence_id':'s1','kind':'subtitle','text':'带宽影响数据传输'}]}
    record=plugin.companion.video_study(packet,{'study_question':question,'reflection_evidence_ids':['s1']})
    assert record and not plugin.owner_notebook.related('group','显存带宽')
    search=AsyncMock(return_value={'results':[{'summary':'数据传输受带宽影响','url':'https://example.org/source'}]})
    monkeypatch.setattr('astrbot_plugin_fish_capabilities.services.public_search.search',search)
    plugin.context=type('Ctx',(),{'get_config':lambda self:{}})()
    plugin.private_generate=AsyncMock(return_value='{"content":"带宽影响传输，推理还取决于其他因素","evidence":"数据传输受带宽影响"}')
    result=await plugin.autonomy_action('learn','study:'+str(record['id']),{})
    assert result['revision']==2 and search.await_args.args[1]==question
    note=plugin.owner_notebook.related(scope,'今天讲到显存带宽')[0]
    assert note['source']['url'].endswith('/source')
    plugin.owner_notebook.study_save(scope,question,'修正后的说法',{'type':'owner_statement'},'corrected',note['id'],2)
    assert plugin.owner_notebook.related(scope,question)[0]['body']=='修正后的说法'
    with pytest.raises(CapabilityError):plugin.owner_notebook.study_save(scope,question,'过期结果',{},'provisional',note['id'],2)
    assert plugin.owner_notebook.claim_question(scope,note['id']) is None
