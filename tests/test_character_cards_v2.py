import json,hashlib
from PIL import Image
from astrbot_plugin_fish_capabilities.services.character_atlas import CharacterAtlas

def test_migrate_hot_reload_disable_remove_and_bad_file(tmp_path):
 c={'id':'one','family':'test','display_name':'一号','status':'priority_reference','references':['ref'],'visual_features':['blue'],'disambiguation':['not person'],'aliases':['一号']}
 p=tmp_path/'one.png';Image.new('RGB',(10,10),'blue').save(p)
 ref={'file':p.name,'visually_checked':True,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
 (tmp_path/'cards.json').write_text(json.dumps({'cards':[c],'references':{'ref':ref},'meme_notes':[]}))
 a=CharacterAtlas(tmp_path);assert a.migrate()==1
 assert (tmp_path/'cards.json.pre-cards-v2.bak').exists()
 assert len(a.bundle()[0])==1
 revision=a.fingerprint()
 a.set_enabled('one',False);assert a.bundle()==([],[]) and not a.notes_for_text('一号')
 assert a.fingerprint()!=revision
 a.set_enabled('one',True);assert len(a.bundle()[0])==1
 doc=json.loads((tmp_path/'cards/one.json').read_text());doc['card']['display_name']='新称呼'
 (tmp_path/'cards/one.json').write_text(json.dumps(doc))
 assert a.notes_for_text('新称呼')['cards'][0]['name']=='新称呼'
 (tmp_path/'cards/broken.json').write_text('{bad')
 assert len(a.bundle()[0])==1 and a.load_errors==['broken.json']
 (tmp_path/'cards/one.json').unlink();assert a.bundle()==([],[])

def test_more_than_six_prioritizes_title_alias(tmp_path):
 p=tmp_path/'r.png';Image.new('RGB',(8,8),'blue').save(p)
 refs={'r':{'file':p.name,'visually_checked':True,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}}
 cards=[{'id':str(i),'family':'test','display_name':'角色'+str(i),'aliases':['专名'+str(i)],'status':'priority_reference','references':['r']} for i in range(8)]
 (tmp_path/'cards.json').write_text(json.dumps({'cards':cards,'references':refs}))
 a=CharacterAtlas(tmp_path);assert a.bundle('专名7介绍')[0][0]['character_id']=='7'
