import hashlib
import json
from pathlib import Path

from astrbot_plugin_fish_capabilities.services.character_atlas import CharacterAtlas


def test_atlas_only_hash_checked_priority_references(tmp_path):
    from PIL import Image
    image=tmp_path/'ref.png';Image.new('RGB',(20,20),'blue').save(image)
    ref={'file':'ref.png','visually_checked':True,'sha256':hashlib.sha256(image.read_bytes()).hexdigest()}
    c={'id':'deepseek.test','family':'DeepSeek','display_name':'鲸鱼娘','status':'priority_reference','visual_features':['鲸尾','鳍发束'],'disambiguation':['不等于小鲸'],'references':['r']}
    data={'cards':[c,dict(c,id='unverified',status='source_index_only')],'references':{'r':ref}}
    (tmp_path/'cards.json').write_text(json.dumps(data),encoding='utf-8')
    cards,paths=CharacterAtlas(tmp_path).bundle()
    assert len(cards)==len(paths)==1
    image.write_bytes(b'changed')
    assert CharacterAtlas(tmp_path).bundle()==([],[])


def test_matches_cannot_claim_reference_image_or_account():
    cards=[{'character_id':'gpt.dragon','name':'GPT龙娘','family':'GPT'}]
    shown=[{'id':'f1','time':10}]
    valid={'character_id':'gpt.dragon','frame_ids':['f1'],'confidence':.95,'evidence':'画面中同时可见白色龙角和有鳞片的龙尾'}
    result=CharacterAtlas.matches({'characters':[valid]},shown,cards)
    assert len(result)==1 and not result[0]['is_xiaojing_verified'] and not result[0]['account_identity_verified']
    for edit in [{'character_id':'invented'},{'frame_ids':['reference1']},{'confidence':.5},{'confidence':True},{'evidence':'白发'}]:
        assert CharacterAtlas.matches({'characters':[dict(valid,**edit)]},shown,cards)==[]


def test_six_reviewed_characters_are_not_silently_capped_at_three(tmp_path):
    from PIL import Image
    image=tmp_path/'ref.png';Image.new('RGB',(20,20),'blue').save(image)
    ref={'file':'ref.png','visually_checked':True,'sha256':hashlib.sha256(image.read_bytes()).hexdigest()}
    cards=[{'id':'test.'+str(i),'family':'public','display_name':'test '+str(i),'status':'priority_reference','visual_features':['marked shape'],'disambiguation':['not account'],'references':['r']} for i in range(7)]
    (tmp_path/'cards.json').write_text(json.dumps({'cards':cards,'references':{'r':ref}}))
    loaded,paths=CharacterAtlas(tmp_path).bundle();assert len(loaded)==len(paths)==6


def test_meme_notes_require_relevant_character_and_context(tmp_path):
    data={'cards':[{'id':'zzz.small','display_name':'小挽昼','family':'ZenlessZoneZero','status':'priority_reference','aliases':['小挽昼'],'visual_features':[],'public_notes':[]}],
          'meme_notes':[{'id':'pun','character_ids':['zzz.small'],'aliases':['三碗粥'],'meaning':'community pun','kind':'editorial','source':'https://example.com','checked_at':'2026-10-28'}]}
    (tmp_path/'cards.json').write_text(json.dumps(data))
    atlas=CharacterAtlas(tmp_path)
    assert not atlas.notes_for_text('早饭吃了三碗粥')
    assert atlas.notes_for_text('三碗粥是什么梗')['meme_context'][0]['id']=='pun'
    assert not atlas.meme_context([{'character_id':'gpt.dragon'}],'三碗粥')


def test_missing_atlas_notes_are_optional(tmp_path):
    atlas=CharacterAtlas(tmp_path)
    assert atlas.notes_for_text('小挽昼')=={} and atlas.meme_context([],'挽昼')==[]
