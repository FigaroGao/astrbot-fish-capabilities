import json,types
from pathlib import Path
from unittest.mock import AsyncMock
import pytest
from astrbot_plugin_fish_capabilities.services.knowledge import PublicKnowledge

@pytest.fixture
def kb(tmp_path):
    entries=[{'id':'agent-1','aliases':['Cypher','零'],'title':'零 / Cypher','text':'国服名称零','source':'https://val.qq.com/'},{'id':'meme-1','aliases':['感谢现役'],'title':'感谢现役','text':'社区用语','source':'https://www.bilibili.com/'},{'id':'champions-2026','aliases':['2026','Champions'],'title':'2026赛果','text':'历史','source':'https://valorantesports.com/'}]
    p=tmp_path/'entries.json';p.write_text(json.dumps(entries),encoding='utf-8')
    manager=types.SimpleNamespace(retrieve=AsyncMock(return_value={'results':[{'doc_name':'public','content':'核对日期2026-10-24，社区用语'}]}))
    return PublicKnowledge(types.SimpleNamespace(kb_manager=manager),{'knowledge_names':['public']},p)

def test_topic_query_does_not_send_private_sentences_or_match_year_alone(kb):
    assert kb.query_for('我2026年要考试')==''
    assert kb.query_for('我和妈妈吵架了，想问Cypher国服叫什么')=='Cypher 国服'
    assert kb.query_for('英雄联盟LPL感谢现役')==''
    assert kb.query_for('package')==''

async def test_public_retrieval_cached_and_scoped_to_configured_kb(kb):
    result=await kb.search('感谢现役')
    assert '历史' in result['instruction']
    await kb.search('感谢现役')
    manager=kb.context.kb_manager;manager.retrieve.assert_awaited_once()
    assert manager.retrieve.await_args.kwargs['kb_names']==['public']

async def test_catalog_does_not_require_embedding(kb):
    result=await kb.search('全部国服特工名称')
    assert len(result['catalog'])==1 and result['catalog'][0]['title']=='零 / Cypher'
    kb.context.kb_manager.retrieve.assert_not_awaited()
