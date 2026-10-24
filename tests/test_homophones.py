from pathlib import Path
import json
import pytest
from astrbot_plugin_fish_capabilities.services.homophones import HomophoneHints
from test_knowledge import kb


@pytest.fixture
def hints():
    return HomophoneHints(Path(__file__).parents[1]/'astrbot_plugin_fish_capabilities/language_aliases.json')


@pytest.mark.parametrize('text,expected',[
    ('这视频针不戳','真不错'),('尊嘟假嘟？','真的假的'),
    ('你今天好稀饭这个吗','喜欢'),('真是栓Q了','谢谢'),
    ('下线啦886','拜拜'),('dbq我忘了','对不起'),
])
def test_known_conversational_candidates(hints,text,expected):
    assert expected in json.dumps(hints.hints(text),ensure_ascii=False)


@pytest.mark.parametrize('text',[
    '今晚吃稀饭','芜湖明天天气','验证码886','订单号是88',
    'https://example.org/尊嘟假嘟','`针不戳`','```python\nxswl=1\n```',
    '文件名 尊嘟假嘟.json','my_dbq_account',
])
def test_literals_names_numbers_and_code_are_not_corrected(hints,text):
    assert hints.hints(text)==[]


def test_reference_is_bounded_and_does_not_grant_authority(hints):
    text='尊嘟假嘟 针不戳 泰裤辣 蚌不住 夺笋 栓Q 耗丸 布吉岛 蟹蟹 gkd'
    assert len(hints.hints(text))==6
    assert '权限' in hints.reference(text) and '长期记忆' in hints.reference(text)


async def test_common_slang_routes_to_public_slang_collection_without_private_sentence(kb):
    kb.entries.append({'id':'common-1','aliases':['尊嘟假嘟'],'title':'尊嘟假嘟'})
    kb.config['slang_knowledge_names']=['public_slang']
    query=kb.query_for('我私下的秘密不告诉别人，尊嘟假嘟什么意思')
    assert query=='尊嘟假嘟 什么意思'
    await kb.search(query)
    assert kb.context.kb_manager.retrieve.await_args.kwargs['kb_names']==['public_slang']
    assert kb.collections('Cypher 国服')==['public']
    assert kb.collections('VCT 尊嘟假嘟')==['public','public_slang']
    assert kb.collections('没收录的新词是什么梗')==['public_slang']
    assert kb.collections('感谢现役是什么梗')==['public']


def test_common_slang_is_not_suppressed_by_other_game_but_game_memes_are(kb):
    kb.entries.append({'id':'common-1','aliases':['尊嘟假嘟'],'title':'尊嘟假嘟'})
    assert kb.query_for('LPL感谢现役')==''
    assert kb.query_for('LPL，尊嘟假嘟')=='尊嘟假嘟'
    assert kb.query_for('`尊嘟假嘟`')==''
