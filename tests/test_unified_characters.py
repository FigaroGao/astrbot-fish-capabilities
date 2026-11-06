import json,types
from unittest.mock import AsyncMock
import pytest
from astrbot_plugin_fish_capabilities.services.character_atlas import CharacterAtlas
from astrbot_plugin_fish_capabilities.services.knowledge import PublicKnowledge

@pytest.mark.asyncio
async def test_unified_profile_hot_edit_disable_archive_and_noncharacter_retention(tmp_path):
 root=tmp_path/'atlas';root.mkdir();(root/'cards.json').write_text('{"cards":[],"references":{}}')
 manifest=tmp_path/'public.json'
 agent={'id':'agent-1','title':'示例 / Demo','aliases':['示例','Demo'],'text':'最初知识','source':'https://example.com','checked_at':'2026-11-03'}
 other={'id':'map-1','title':'地图','aliases':['地图'],'text':'地图资料','source':'https://example.com'}
 manifest.write_text(json.dumps([agent,other]));a=CharacterAtlas(root)
 assert a.unify_knowledge(manifest)['moved']==1
 assert json.loads(manifest.read_text())==[other]
 assert a.unify_knowledge(manifest)['moved']==0
 manager=types.SimpleNamespace(retrieve=AsyncMock(return_value={'results':[]}))
 kb=PublicKnowledge(types.SimpleNamespace(kb_manager=manager),{'knowledge_names':['public']},manifest);kb.characters=a
 assert '最初知识' in (await kb.search('Demo'))['results'][0]['content']
 path=root/'cards/valorant.agent-1.json';doc=json.loads(path.read_text())
 doc['card']['knowledge'][0]['text']='纠正后的知识';path.write_text(json.dumps(doc))
 assert (await kb.search('示例'))['results'][0]['content']=='纠正后的知识'
 assert a.notes_for_text('示例')['cards'][0]['notes']==['纠正后的知识']
 assert a.bundle()==([],[])  # Text-only records do not invent visual references.
 assert len((await kb.search('全部特工名称'))['catalog'])==1
 a.set_enabled('valorant.agent-1',False)
 assert not (await kb.search('Demo'))['results']
 assert not (await kb.search('全部特工名称'))['catalog']
 path.rename(path.with_suffix('.json.removed'))
 assert not (await kb.search('Demo'))['results']
 manager.retrieve.assert_not_awaited()

def test_existing_visual_card_reused_when_agent_alias_matches(tmp_path):
 root=tmp_path/'atlas';root.mkdir();(root/'cards.json').write_text('{"cards":[],"references":{}}');(root/'cards').mkdir()
 p=root/'cards/valorant.hush.json';p.write_text(json.dumps({'card':{'id':'valorant.hush','family':'VALORANT','display_name':'遐思','aliases':['Hush'],'status':'priority_reference','references':[]},'references':{}}))
 m=tmp_path/'k.json';m.write_text(json.dumps([{'id':'agent-30','title':'遐思 / Hush','aliases':['遐思','Hush'],'text':'官方更新','source':'https://example.com'}]))
 a=CharacterAtlas(root);assert a.unify_knowledge(m)['profiles']==1
 assert a.knowledge_entries()[0]['character_id']=='valorant.hush'

def test_empty_knowledge_and_visual_switch_are_independent(tmp_path):
 from PIL import Image
 import hashlib
 root=tmp_path/'atlas';root.mkdir();(root/'cards').mkdir()
 p=root/'ref.png';Image.new('RGB',(8,8),'blue').save(p)
 path=root/'cards/demo.json'
 path.write_text(json.dumps({'card':{'id':'demo','family':'test','display_name':'示例','status':'priority_reference','references':['r'],'knowledge':[],'visual_enabled':False},'references':{'r':{'file':'ref.png','visually_checked':True,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}}}))
 a=CharacterAtlas(root);a.normalize_profiles()
 assert a.knowledge_entries()[0]['text'].endswith('文字知识内容留空，不补猜。')
 assert a.bundle()==([],[])
 a.set_visual_enabled('demo',True);assert len(a.bundle()[0])==1
 assert a.knowledge_entries()[0]['text'].endswith('文字知识内容留空，不补猜。')
