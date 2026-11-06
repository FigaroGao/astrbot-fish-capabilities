"""Local character-card management. No model calls, downloads or account changes."""
import argparse,json,importlib.util
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True,help='character-atlas data directory')
 p.add_argument('--plugin-dir',type=Path)
 p.add_argument('action',choices=['list','migrate','show','put','enable','disable','visual-enable','visual-disable','remove']);p.add_argument('value',nargs='?',default='')
 a=p.parse_args();src=(a.plugin_dir or Path(__file__).resolve().parents[1]/'astrbot_plugin_fish_capabilities')/'services/character_atlas.py'
 spec=importlib.util.spec_from_file_location('card_management',src);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 atlas=m.CharacterAtlas(a.root);a.root.mkdir(parents=True,exist_ok=True)
 if a.action=='list':
  atlas.migrate();rows=[]
  for f in sorted((a.root/'cards').glob('*.json')):
   try:
    c=json.loads(f.read_text(encoding='utf-8-sig'))['card'];rows.append({'id':c['id'],'name':c['display_name'],'enabled':c.get('enabled',True),'visual_enabled':c.get('visual_enabled',False),'knowledge_entries':len(c.get('knowledge',[])),'status':c.get('status')})
   except (ValueError,KeyError):rows.append({'file':f.name,'invalid':True})
  print(json.dumps(rows,ensure_ascii=False,indent=2));return
 if a.action=='migrate':print(atlas.migrate());return
 if a.action=='put':
  doc=json.loads(Path(a.value).read_text(encoding='utf-8-sig'));c=doc.get('card')
  if not atlas.valid(c):raise ValueError('invalid_card')
  c.setdefault('knowledge',[]);c.setdefault('visual_enabled',False)
  atlas.migrate();folder=a.root/'cards';folder.mkdir(exist_ok=True)
  dest=folder/(c['id']+'.json');tmp=dest.with_suffix('.tmp')
  tmp.write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(dest);print('saved',c['id']);return
 atlas.migrate()
 import re
 if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,95}',a.value):raise ValueError('invalid_id')
 path=a.root/'cards'/(a.value+'.json')
 if a.action=='show':print(path.read_text(encoding='utf-8'))
 elif a.action in ('enable','disable'):atlas.set_enabled(a.value,a.action=='enable');print('updated',a.value)
 elif a.action in ('visual-enable','visual-disable'):atlas.set_visual_enabled(a.value,a.action=='visual-enable');print('visual_updated',a.value)
 elif a.action=='remove':
  backup=path.with_suffix('.json.removed')
  if backup.exists():raise ValueError('archive_already_exists')
  path.rename(backup);print('archived',a.value)
if __name__=='__main__':main()
