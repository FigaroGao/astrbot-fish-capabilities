import json
from pathlib import Path
from astrbot_plugin_fish_capabilities.services.knowledge import PublicKnowledge

async def test_curated_definitions_use_primary_source_without_vector_call(tmp_path):
    rows=json.loads((Path(__file__).parents[1]/'knowledge/conversation/entries.json').read_text(encoding='utf-8'))
    path=tmp_path/'entries.json';path.write_text(json.dumps(rows),encoding='utf-8')
    knowledge=PublicKnowledge(None,{},path)
    result=await knowledge.search('鱼八股是什么意思')
    assert result['results'][0]['kind']=='curated_update'
    assert result['results'][0]['checked_at']=='2026-11-06'
    assert '不能混称官方事实' in result['instruction']
    result=await knowledge.search('fishtalk的文风包')
    assert result['results'][0]['source'].startswith('https://github.com/Nozzi2455/')
