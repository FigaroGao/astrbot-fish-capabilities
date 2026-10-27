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
