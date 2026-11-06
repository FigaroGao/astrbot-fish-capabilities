"""Small reviewed public character references; never map appearance to an account."""
import hashlib
import json
import math
import re
from pathlib import Path

class CharacterAtlas:
    def __init__(self,root):self.root=Path(root)

    @staticmethod
    def valid(card):
        return (isinstance(card,dict) and isinstance(card.get('id'),str)
            and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,95}',card['id'])
            and all(isinstance(card.get(k),str) and 1<=len(card[k])<=160 for k in ('display_name','family'))
            and all(isinstance(card.get(k,[]),list) and len(card.get(k,[]))<=40 and all(isinstance(x,str) and len(x)<=2000 for x in card.get(k,[])) for k in ('aliases','visual_features','disambiguation','references','public_notes')))

    @staticmethod
    def rank(card,query):
        q=str(query).casefold()[:6000]
        hit=any(len(a)>=2 and a.casefold() in q for a in card.get('aliases',[])+[card.get('display_name','')])
        priority=card.get('priority',0)
        return (hit,priority if type(priority)is int and -100<=priority<=100 else 0)

    def load(self):
        try:
            p=self.root/'cards.json'
            data=json.loads(p.read_text(encoding='utf-8-sig')) if p.is_file() and p.stat().st_size<2000000 else {}
        except (OSError,ValueError):data={}
        if not isinstance(data,dict):data={}
        result=dict(data);references=dict(data.get('references',{}));cards={c['id']:c for c in data.get('cards',[]) if self.valid(c)}
        self.load_errors=[]
        folder=self.root/'cards'
        for p in sorted(folder.glob('*.json'))[:512]:
            try:
                if p.is_symlink() or p.stat().st_size>100000:raise ValueError('file_invalid')
                doc=json.loads(p.read_text(encoding='utf-8-sig'));c=doc.get('card')
                if not self.valid(c) or p.stem!=c['id']:raise ValueError('card_invalid_or_id_mismatch')
                c=dict(c);refs=doc.get('references',{})
                if not isinstance(refs,dict):raise ValueError('references_invalid')
                c['references']=[c['id']+':'+v for v in c.get('references',[])]
                references.update({c['id']+':'+k:v for k,v in refs.items() if isinstance(k,str) and isinstance(v,dict)})
                cards[c['id']]=c
            except (ValueError,TypeError,OSError,KeyError):self.load_errors.append(p.name)
        result['cards']=[c for c in cards.values() if c.get('enabled',True) is not False]
        result['references']=references
        return result

    def migrate(self):
        path=self.root/'cards.json'
        if not path.is_file():return 0
        data=json.loads(path.read_text(encoding='utf-8-sig'));folder=self.root/'cards';folder.mkdir(exist_ok=True)
        count=0
        for c in data.get('cards',[]):
            if not self.valid(c):raise ValueError('legacy_invalid_card')
            dest=folder/(c['id']+'.json')
            if not dest.exists():
                doc={'schema_version':2,'card':c,'references':{k:data.get('references',{}).get(k,{}) for k in c.get('references',[])}}
                dest.write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8');count+=1
        backup=path.with_suffix('.json.pre-cards-v2.bak')
        if not backup.exists():backup.write_bytes(path.read_bytes())
        data['schema_version']=2;data['cards']=[];data['references']={}
        tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(path)
        return count

    def set_enabled(self,ident,enabled):
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,95}',ident):raise ValueError('invalid_id')
        self.migrate();p=self.root/'cards'/(ident+'.json');doc=json.loads(p.read_text(encoding='utf-8-sig'))
        doc['card']['enabled']=bool(enabled);tmp=p.with_suffix('.tmp')
        tmp.write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(p)

    def set_visual_enabled(self,ident,enabled):
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,95}',ident):raise ValueError('invalid_id')
        p=self.root/'cards'/(ident+'.json');doc=json.loads(p.read_text(encoding='utf-8-sig'))
        doc['card']['visual_enabled']=bool(enabled);tmp=p.with_suffix('.tmp')
        tmp.write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(p)

    def normalize_profiles(self):
        count=0
        for p in (self.root/'cards').glob('*.json'):
            try:
                doc=json.loads(p.read_text(encoding='utf-8-sig'));c=doc['card']
                if not self.valid(c):continue
                c.setdefault('knowledge',[])
                notes=c.get('public_notes',[])
                if notes and not all(any(n in e.get('text','') for e in c['knowledge'] if isinstance(e,dict)) for n in notes):
                    sources=c.get('sources',[])
                    c['knowledge'].append({'id':'character-note-'+c['id'],'title':c['display_name'],'aliases':c.get('aliases',[]),'text':'；'.join(notes),'source':next((s for s in sources if isinstance(s,str)),'原角色卡已存文字资料'),'checked_at':c.get('checked_at','未记录')})
                c['public_notes']=[]
                c.setdefault('visual_enabled',c.get('status')=='priority_reference' and bool(c.get('references')))
                doc['schema_version']=3;tmp=p.with_suffix('.tmp')
                tmp.write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(p);count+=1
            except (ValueError,OSError,KeyError):continue
        return count

    def unify_knowledge(self,manifest):
        """One-time/idempotent move of agent text into the canonical profiles."""
        self.root.mkdir(parents=True,exist_ok=True);self.migrate()
        entries=json.loads(Path(manifest).read_text(encoding='utf-8-sig'))
        folder=self.root/'cards';folder.mkdir(exist_ok=True)
        docs={}
        for p in folder.glob('*.json'):
            try:
                doc=json.loads(p.read_text(encoding='utf-8-sig'))
                if self.valid(doc.get('card')):docs[p]=doc
            except (OSError,ValueError):continue
        moved=[];remaining=[]
        for entry in entries:
            if not re.fullmatch(r'agent-[0-9]+',str(entry.get('id',''))):remaining.append(entry);continue
            aliases=set(entry.get('aliases',[]))
            selected=next(((p,d) for p,d in docs.items() if d['card'].get('family')=='VALORANT' and aliases.intersection(d['card'].get('aliases',[])+[d['card'].get('display_name','')])),None)
            if selected:p,doc=selected
            else:
                ident='valorant.'+entry['id'];p=folder/(ident+'.json')
                doc={'schema_version':3,'card':{'id':ident,'family':'VALORANT','display_name':entry['title'].split(' / ')[0],'aliases':entry.get('aliases',[]),'enabled':True,'status':'knowledge_only','visual_features':[],'disambiguation':[],'references':[],'public_notes':[],'checked_at':entry.get('checked_at')},'references':{}}
            existing=[e for e in doc['card'].get('knowledge',[]) if e.get('id')!=entry['id']]
            doc['card']['knowledge']=existing+[entry];doc['schema_version']=3
            tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(p);docs[p]=doc;moved.append(entry['id'])
        manifest=Path(manifest);backup=manifest.with_suffix('.pre-unified-characters.bak')
        if not backup.exists():backup.write_bytes(manifest.read_bytes())
        tmp=manifest.with_suffix('.tmp');tmp.write_text(json.dumps(remaining,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(manifest)
        return {'moved':len(moved),'remaining_noncharacter_entries':len(remaining),'profiles':len(docs)}

    def fingerprint(self):
        data=self.load();stamps=[]
        for ref in data.get('references',{}).values():
            name=ref.get('file','')
            if isinstance(name,str) and Path(name).name==name:
                p=self.root/name
                if p.is_file():stamps.append((name,p.stat().st_size,p.stat().st_mtime_ns))
        return hashlib.sha256(json.dumps([data,stamps],sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:20]

    def knowledge_entries(self):
        """Text projection of the same enabled files used for visual references."""
        result=[]
        for card in self.load()['cards']:
            knowledge=card.get('knowledge',[])
            if isinstance(knowledge,list) and knowledge:
                for entry in knowledge[:40]:
                    if not isinstance(entry,dict) or not all(isinstance(entry.get(k),str) for k in ('id','title','text','source')):continue
                    result.append(dict(entry,title=card['display_name'],aliases=list(dict.fromkeys([card['display_name']]+card.get('aliases',[]))),character_id=card['id']))
            else:
                sources=card.get('sources',[])
                result.append({'id':'character-'+card['id'],'character_id':card['id'],'title':card['display_name'],
                    'aliases':list(dict.fromkeys([card['display_name']]+card.get('aliases',[]))),
                    'text':'名称：'+card['display_name']+'；所属：'+card['family']+'。文字知识内容留空，不补猜。',
                    'source':next((s for s in sources if isinstance(s,str)),'本机已审核角色档案'),
                    'checked_at':card.get('checked_at','未记录')})
        return result

    def inactive_aliases_match(self,query):
        """Disabled/archived cards must not fall back to stale vector documents."""
        active={c['id'] for c in self.load()['cards']}
        folder=self.root/'cards'
        for p in list(folder.glob('*.json'))[:512]+list(folder.glob('*.json.removed'))[:512]:
            try:
                if p.stat().st_size>100000:continue
                card=json.loads(p.read_text(encoding='utf-8-sig'))['card']
                if card.get('id') in active:continue
                if any(len(a)>=2 and re.search(r'(?<![A-Za-z0-9_])'+re.escape(a)+r'(?![A-Za-z0-9_])' if a.isascii() else re.escape(a),query,re.I) for a in [card.get('display_name','')]+card.get('aliases',[])):return True
            except (ValueError,KeyError,TypeError,OSError):continue
        return False

    def bundle(self,query=""):
        data=self.load()
        rows=[];paths=[]
        for card in sorted(data.get('cards',[]),key=lambda c: self.rank(c,query),reverse=True):
            if not card.get('visual_enabled',card.get('status')=='priority_reference') or len(rows)>=6:continue
            ref=data['references'].get((card.get('references') or [None])[0],{})
            if ref.get('visually_checked') is not True:continue
            filename=ref.get('file','')
            if not isinstance(filename,str) or Path(filename).name!=filename or Path(filename).suffix.lower() not in ('.png','.jpg','.jpeg'):continue
            path=(self.root/filename).resolve()
            if path.parent!=self.root.resolve() or not path.is_file() or path.stat().st_size>8_000_000:continue
            if hashlib.sha256(path.read_bytes()).hexdigest()!=ref.get('sha256'):continue
            paths.append(path)
            rows.append({'character_id':card['id'],'family':card['family'],'name':card['display_name'],
                         'features':card.get('visual_features',[]),'disambiguation':card.get('disambiguation',[]),'forms':card.get('forms',[]),
                         'reference_number':len(paths),'view_limitation':ref.get('view','')})
        return rows,paths

    def notes_for_text(self,text):
        try:data=self.load()
        except (OSError,ValueError):return {}
        if not isinstance(data,dict):return {}
        text=str(text)[:3000].casefold();cards=[]
        for card in data.get('cards',[]):
            aliases=card.get('aliases',[])+[card.get('display_name','')]
            if card.get('status') in ('priority_reference','knowledge_only') and any(isinstance(a,str) and len(a)>=2 and a.casefold() in text for a in aliases):
                cards.append({'id':card['id'],'name':card['display_name'],'family':card['family'],'features':card.get('visual_features',[]),'notes':[e['text'][:1600] for e in self.knowledge_entries() if e['character_id']==card['id']]})
        if not cards and re.search('什么梗|啥梗|绝区零|挽昼',text):
            ids={cid for n in data.get('meme_notes',[]) if any(a.casefold() in text for a in n.get('aliases',[])) for cid in n.get('character_ids',[])}
            cards=[{'id':c['id'],'name':c['display_name'],'family':c['family'],'features':c.get('visual_features',[]),'notes':c.get('public_notes',[])} for c in data.get('cards',[]) if c.get('id') in ids and c.get('status')=='priority_reference']
        return {'cards':cards[:6],'meme_context':self.meme_context([{'character_id':c['id']} for c in cards],text)} if cards else {}

    def meme_context(self,matches,text=''):
        try:data=self.load()
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
