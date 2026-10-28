"""Small reviewed public character references; never map appearance to an account."""
import hashlib
import json
import math
import re
from pathlib import Path

class CharacterAtlas:
    def __init__(self,root):self.root=Path(root)

    def bundle(self):
        data=json.loads((self.root/'cards.json').read_text(encoding='utf-8'))
        rows=[];paths=[]
        for card in data.get('cards',[]):
            if card.get('status')!='priority_reference' or len(rows)>=6:continue
            ref=data['references'].get(card.get('references',[None])[0],{})
            if ref.get('visually_checked') is not True:continue
            filename=ref.get('file','')
            if not isinstance(filename,str) or Path(filename).name!=filename or Path(filename).suffix.lower() not in ('.png','.jpg','.jpeg'):continue
            path=(self.root/filename).resolve()
            if path.parent!=self.root.resolve() or not path.is_file() or path.stat().st_size>8_000_000:continue
            if hashlib.sha256(path.read_bytes()).hexdigest()!=ref.get('sha256'):continue
            paths.append(path)
            rows.append({'character_id':card['id'],'family':card['family'],'name':card['display_name'],
                         'features':card['visual_features'],'disambiguation':card['disambiguation'],'forms':card.get('forms',[]),
                         'reference_number':len(paths),'view_limitation':ref.get('view','')})
        return rows,paths

    def notes_for_text(self,text):
        try:data=json.loads((self.root/'cards.json').read_text(encoding='utf-8'))
        except (OSError,ValueError):return {}
        if not isinstance(data,dict):return {}
        text=str(text)[:3000].casefold();cards=[]
        for card in data.get('cards',[]):
            aliases=card.get('aliases',[])+[card.get('display_name','')]
            if card.get('status')=='priority_reference' and any(isinstance(a,str) and len(a)>=2 and a.casefold() in text for a in aliases):
                cards.append({'id':card['id'],'name':card['display_name'],'family':card['family'],'features':card.get('visual_features',[]),'notes':card.get('public_notes',[])})
        if not cards and re.search('什么梗|啥梗|绝区零|挽昼',text):
            ids={cid for n in data.get('meme_notes',[]) if any(a.casefold() in text for a in n.get('aliases',[])) for cid in n.get('character_ids',[])}
            cards=[{'id':c['id'],'name':c['display_name'],'family':c['family'],'features':c.get('visual_features',[]),'notes':c.get('public_notes',[])} for c in data.get('cards',[]) if c.get('id') in ids and c.get('status')=='priority_reference']
        return {'cards':cards[:6],'meme_context':self.meme_context([{'character_id':c['id']} for c in cards],text)} if cards else {}

    def meme_context(self,matches,text=''):
        try:data=json.loads((self.root/'cards.json').read_text(encoding='utf-8'))
        except (OSError,ValueError):return []
        if not isinstance(data,dict):return []
        ids={m.get('character_id') for m in matches if isinstance(m,dict)};notes=[]
        for note in data.get('meme_notes',[]):
            if not ids.intersection(note.get('character_ids',[])):continue
            if note.get('aliases') and not any(a.casefold() in str(text).casefold() for a in note['aliases']):continue
            notes.append({k:note.get(k) for k in ('id','meaning','kind','source','checked_at')})
        return notes[:3]

    @staticmethod
    def matches(plan,shown,cards,source='initial_sampled_preview'):
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
                            'visible_evidence':evidence.strip(),'source':source,
                            'account_identity_verified':False,'is_xiaojing_verified':False,
                            'limitation':'视觉模型与参考图匹配，仍可能认错；不证明具体账号、个人身份或二创关系。'})
            seen.add(ident)
        return results


def compact_matches(rows):
    """Keep names and actual-frame evidence when large tool output is shortened."""
    if not isinstance(rows,list):return []
    result=[]
    for row in rows[:6]:
        if not isinstance(row,dict):continue
        item={k:row[k] for k in ('character_id','name','family','confidence','source') if k in row}
        if not isinstance(item.get('character_id'),str) or not isinstance(item.get('name'),str):continue
        item['visible_evidence']=str(row.get('visible_evidence',''))[:180]
        item['frame_ids']=row.get('frame_ids',[])[:6] if isinstance(row.get('frame_ids'),list) else []
        item['account_identity_verified']=False;item['is_xiaojing_verified']=False
        result.append(item)
    return result
