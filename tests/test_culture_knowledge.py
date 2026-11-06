import json
from pathlib import Path
import pytest
from astrbot_plugin_fish_capabilities.services.knowledge import PublicKnowledge


@pytest.mark.parametrize('query,ident',[
    ('吃谷是什么意思','common-culture-goods'),
    ('她说我的话是预制回复','common-culture-prefabricated'),
    ('基础不基础这个梗','common-culture-basic-contrast'),
])
async def test_culture_terms_have_dated_source_and_no_vector_call(tmp_path,query,ident):
    source=Path(__file__).parents[1]/'knowledge/culture/entries.json'
    rows=json.loads(source.read_text(encoding='utf-8'))
    assert len({r['id'] for r in rows})==len(rows)
    assert all(r['source_published_at']=='2025-12-26' for r in rows)
    kb=PublicKnowledge(None,{},source)
    result=await kb.search(query)
    assert result['results'][0]['source_document']==next(r['title'] for r in rows if r['id']==ident)
    assert result['results'][0]['checked_at']=='2026-11-06'
    assert '不能混称官方事实' in result['instruction']
