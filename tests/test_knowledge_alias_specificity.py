from types import SimpleNamespace
from astrbot_plugin_fish_capabilities.services.knowledge import PublicKnowledge,alias_rows


def rows():
    return [dict(id=str(i),title=name,aliases=[name,'挽昼'],text=name,source='local',character_id=str(i))
            for i,name in enumerate(('大挽昼','中挽昼','小挽昼'))]


def test_specific_name_does_not_recall_all_family_members():
    assert [e['title'] for e in alias_rows(rows(),'小挽昼是谁')]==['小挽昼']


def test_family_query_remains_ambiguous_and_separate_mentions_are_retained():
    assert len(alias_rows(rows(),'挽昼是谁'))==3
    assert [e['title'] for e in alias_rows(rows(),'小挽昼和大挽昼')]==['大挽昼','小挽昼']
    assert len(alias_rows(rows(),'小挽昼与其他挽昼') )==3


def test_ascii_alias_does_not_match_inside_identifier():
    entries=[{'aliases':['GPT']},{'aliases':['GPT姐姐']}]
    assert not alias_rows(entries,'myGPT_identifier')
    assert alias_rows(entries,'GPT姐姐')==[entries[1]]


async def test_role_projection_uses_specificity_without_vector_request(tmp_path):
    knowledge=PublicKnowledge(None,{},tmp_path/'missing.json')
    knowledge.characters=SimpleNamespace(knowledge_entries=rows,inactive_aliases_match=lambda q:False)
    result=await knowledge.search('小挽昼是谁')
    assert [r['source_document'] for r in result['results']]==['小挽昼']
