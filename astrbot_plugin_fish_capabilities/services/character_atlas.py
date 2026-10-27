"""Small reviewed public character references; never map appearance to an account."""
import hashlib
import json
import math
from pathlib import Path

class CharacterAtlas:
    def __init__(self,root):self.root=Path(root)

    def bundle(self):
        data=json.loads((self.root/'cards.json').read_text(encoding='utf-8'))
        rows=[];paths=[]
        for card in data.get('cards',[]):
            if card.get('status')!='priority_reference' or len(rows)>=3:continue
            ref=data['references'].get(card.get('references',[None])[0],{})
            if ref.get('visually_checked') is not True:continue
            filename=ref.get('file','')
            if not isinstance(filename,str) or Path(filename).name!=filename or Path(filename).suffix.lower() not in ('.png','.jpg','.jpeg'):continue
            path=(self.root/filename).resolve()
            if path.parent!=self.root.resolve() or not path.is_file() or path.stat().st_size>8_000_000:continue
            if hashlib.sha256(path.read_bytes()).hexdigest()!=ref.get('sha256'):continue
            paths.append(path)
            rows.append({'character_id':card['id'],'family':card['family'],'name':card['display_name'],
                         'features':card['visual_features'],'disambiguation':card['disambiguation'],
                         'reference_number':len(paths),'view_limitation':ref.get('view','')})
        return rows,paths

    @staticmethod
    def matches(plan,shown,cards):
        allowed={c['character_id']:c for c in cards};frames={p['id']:p['time'] for p in shown}
        results=[];seen=set();rows=plan.get('characters',[])
        if not isinstance(rows,list):return []
        for row in rows[:12]:
            if not isinstance(row,dict) or not isinstance(row.get('character_id'),str):continue
            ident=row['character_id'];card=allowed.get(ident);ids=row.get('frame_ids');score=row.get('confidence');evidence=row.get('evidence')
            if not card or ident in seen or not isinstance(ids,list) or not ids or len(ids)>27:continue
            if not all(isinstance(x,str) and x in frames for x in ids):continue
            if type(score) not in (int,float) or not math.isfinite(score) or not .85<=score<=1:continue
            if not isinstance(evidence,str) or not 8<=len(evidence.strip())<=400:continue
            results.append({'character_id':ident,'name':card['name'],'family':card['family'],
                            'frame_ids':ids,'timestamps':[frames[x] for x in ids],'confidence':score,
                            'visible_evidence':evidence.strip(),'source':'initial_sampled_preview',
                            'account_identity_verified':False,'is_xiaojing_verified':False,
                            'limitation':'视觉模型与参考图匹配，仍可能认错；不证明具体账号、个人身份或二创关系。'})
            seen.add(ident)
        return results
