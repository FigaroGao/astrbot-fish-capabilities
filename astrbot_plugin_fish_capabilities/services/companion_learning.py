"""Small, scoped, reviewable companion records; no extra background model loop."""
import hashlib
import json
import re
import sqlite3
import time
from contextlib import contextmanager
from .activity_timeline import scrub
from .policy import CapabilityError


def terms(text):
    text=str(text).lower()[:3000]
    out=set(re.findall(r'[a-z0-9]{2,}',text))
    for segment in re.findall(r'[\u4e00-\u9fff]+',text):
        out.update(segment[i:i+2] for i in range(len(segment)-1))
    return out


class CompanionLearning:
    def __init__(self,path,clock=time.time):
        self.path,self.clock=path,clock
        with self.db() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS notes(
                id INTEGER PRIMARY KEY,scope TEXT,kind TEXT,topic TEXT,text TEXT,
                source TEXT,state TEXT,stamp REAL,expires REAL,revision INTEGER DEFAULT 1);
                CREATE INDEX IF NOT EXISTS notes_scope ON notes(scope,kind,state);
                CREATE TABLE IF NOT EXISTS revisions(note INTEGER,revision INTEGER,before TEXT,stamp REAL);
                CREATE TABLE IF NOT EXISTS feedback(id INTEGER PRIMARY KEY,scope TEXT,bvid TEXT,
                vote INTEGER,reason TEXT,evidence TEXT,stamp REAL);
                CREATE TABLE IF NOT EXISTS traces(id INTEGER PRIMARY KEY,scope TEXT,stamp REAL,
                kind TEXT,ids TEXT,chars INTEGER);
                CREATE TABLE IF NOT EXISTS migrations(name TEXT PRIMARY KEY);
            ''')

    @contextmanager
    def db(self):
        db=sqlite3.connect(self.path,timeout=5)
        db.row_factory=sqlite3.Row
        try:
            with db:yield db
        finally:db.close()
        self.path.chmod(0o600)

    def save(self,scope,kind,topic,text,source,*,approved=False,note_id=0,revision=0):
        if not scope or kind not in ('style_positive','style_negative','preference','observation','video_insight'):
            raise CapabilityError('记录类型或范围无效。')
        if not isinstance(text,str) or not 1<=len(text.strip())<=600 or not isinstance(topic,str) or len(topic)>80:
            raise CapabilityError('内容限1至600字，场景限80字。')
        if not isinstance(source,dict) or source.get('kind') not in ('owner_statement','owner_review','video_evidence','system_seed','group_statement'):
            raise CapabilityError('需要可核对的来源。')
        if len(json.dumps(source,ensure_ascii=False))>3000:raise CapabilityError('来源过长。')
        now=self.clock();state='approved' if approved else 'pending'
        expiry=now+7*86400 if kind=='observation' else None
        with self.db() as db:
            if note_id:
                old=db.execute('SELECT * FROM notes WHERE id=? AND scope=?',(note_id,scope)).fetchone()
                if old is None or old['revision']!=revision:raise CapabilityError('记录不存在或版本变化，请重新读取。')
                db.execute('INSERT INTO revisions VALUES(?,?,?,?)',(note_id,revision,json.dumps(dict(old),ensure_ascii=False),now))
                db.execute('UPDATE notes SET kind=?,topic=?,text=?,source=?,state=?,stamp=?,expires=?,revision=revision+1 WHERE id=?',
                    (kind,topic,scrub(text.strip()),json.dumps(scrub(source),ensure_ascii=False),state,now,expiry,note_id))
                return {'id':note_id,'revision':revision+1,'state':state}
            duplicate=db.execute('SELECT id,revision,state FROM notes WHERE scope=? AND kind=? AND text=? AND state!=?',
                (scope,kind,scrub(text.strip()),'rejected')).fetchone()
            if duplicate:return dict(duplicate)|{'duplicate':True}
            if db.execute('SELECT COUNT(*) FROM notes WHERE scope=?',(scope,)).fetchone()[0]>=500:
                raise CapabilityError('本范围记录已达500条，请先整理。')
            cur=db.execute('INSERT INTO notes(scope,kind,topic,text,source,state,stamp,expires) VALUES(?,?,?,?,?,?,?,?)',
                (scope,kind,topic,scrub(text.strip()),json.dumps(scrub(source),ensure_ascii=False),state,now,expiry))
            return {'id':cur.lastrowid,'revision':1,'state':state}

    def review(self,scope,ident,state,revision):
        if state not in ('approved','rejected','archived'):raise CapabilityError('审核状态无效。')
        with self.db() as db:
            old=db.execute('SELECT * FROM notes WHERE id=? AND scope=?',(ident,scope)).fetchone()
            if old is None or old['revision']!=revision:raise CapabilityError('记录不存在或版本变化。')
            db.execute('INSERT INTO revisions VALUES(?,?,?,?)',(ident,revision,json.dumps(dict(old),ensure_ascii=False),self.clock()))
            db.execute('UPDATE notes SET state=?,revision=revision+1 WHERE id=?',(state,ident))
        return {'id':ident,'revision':revision+1,'state':state}

    def list(self,scope,kind='',*,include_pending=True,limit=30):
        if type(limit)is not int or not 1<=limit<=100:raise CapabilityError('条数限1至100。')
        with self.db() as db:
            rows=db.execute('SELECT * FROM notes WHERE scope=? AND (?=? OR kind=?) ORDER BY stamp DESC,id DESC LIMIT ?',
                (scope,kind,'',kind,limit)).fetchall()
        output=[]
        for row in rows:
            item=dict(row);item['source']=json.loads(item['source'])
            item['expired']=item['expires'] is not None and item['expires']<=self.clock()
            if include_pending or (item['state']=='approved' and not item['expired']):output.append(item)
        return output

    def recall(self,scope,query,*,kinds=None,limit=4):
        wanted=terms(query);items=self.list(scope,include_pending=False,limit=100)
        scored=[]
        for item in items:
            if kinds and item['kind'] not in kinds:continue
            overlap=len(wanted & terms(item['topic']+' '+item['text']))
            if overlap:scored.append((overlap,item['stamp'],item))
        chosen=[item for _,__,item in sorted(scored,key=lambda r:(r[0],r[1]),reverse=True)[:limit]]
        with self.db() as db:
            db.execute('INSERT INTO traces(scope,stamp,kind,ids,chars) VALUES(?,?,?,?,?)',
                (scope,self.clock(),'learning_recall',json.dumps([x['id'] for x in chosen]),sum(len(x['text']) for x in chosen)))
            db.execute('DELETE FROM traces WHERE stamp<?',(self.clock()-30*86400,))
        return chosen

    def style_hint(self,scope,query):
        rows=self.recall(scope,query,kinds={'style_positive','style_negative'},limit=3)
        if not rows:return ''
        return '[已审核表达参考，仅借鉴场景和说法，不复制经历或固定套句]\n'+json.dumps(
            [{'id':r['id'],'scene':r['topic'],'mode':r['kind'],'text':r['text']} for r in rows],ensure_ascii=False)[:1400]

    def feedback(self,scope,bvid,vote,reason,evidence,current_message):
        if not re.fullmatch(r'BV[0-9A-Za-z]{10}',str(bvid)) or type(vote)is not int or vote not in (-1,0,1):
            raise CapabilityError('需要真实BV号和-1/0/1的反馈。')
        if not isinstance(evidence,str) or len(evidence)<4 or evidence not in current_message:
            raise CapabilityError('反馈必须有主人当前原话依据，不能猜测喜好。')
        with self.db() as db:
            duplicate=db.execute('SELECT id FROM feedback WHERE scope=? AND bvid=? AND evidence=?',
                (scope,bvid,scrub(evidence))).fetchone()
            if duplicate:return {'id':duplicate['id'],'duplicate':True}
            cur=db.execute('INSERT INTO feedback(scope,bvid,vote,reason,evidence,stamp) VALUES(?,?,?,?,?,?)',
                (scope,bvid,vote,scrub(str(reason))[:200],scrub(evidence)[:300],self.clock()))
        return {'id':cur.lastrowid,'saved':True,'instruction':'只是一条带来源的反馈，不把一次反馈当永久偏好。'}

    def feedback_hints(self,scope):
        with self.db() as db:
            rows=db.execute('SELECT bvid,vote,reason,stamp FROM feedback WHERE scope=? AND stamp>? ORDER BY stamp DESC LIMIT 8',
                (scope,self.clock()-30*86400)).fetchall()
        return [dict(row) for row in rows]

    def traces(self,scope,limit=10):
        with self.db() as db:
            return [dict(r,ids=json.loads(r['ids'])) for r in db.execute('SELECT * FROM traces WHERE scope=? ORDER BY id DESC LIMIT ?',
                (scope,max(1,min(20,int(limit)))))]

    def record_recall(self,scope,ids):
        ids=[i for i in ids[:30] if type(i)is int and i>0] if isinstance(ids,list) else []
        with self.db() as db:
            db.execute('INSERT INTO traces(scope,stamp,kind,ids,chars) VALUES(?,?,?,?,?)',
                (scope,self.clock(),'livingmemory_recall',json.dumps(ids),0))
            db.execute('DELETE FROM traces WHERE stamp<?',(self.clock()-30*86400,))

    def seed_style(self,scope):
        key='owner-requested-style-v1:'+scope
        with self.db() as db:
            if db.execute('SELECT 1 FROM migrations WHERE name=?',(key,)).fetchone():return
        for kind,scene,text in [
            ('style_negative','闲聊 认可 同意 我觉得','不要把“这一点我认”“真要只挑一件”当惯用起手式；直接接眼前具体事情，不凭空替对方排唯一重点。'),
            ('style_positive','视频 分享 有意思 好玩','分享视频时聊一个具体感受，留出对方接话的空间；不发完整评论总结，也不要求对方一定看。'),
            ('style_positive','倾诉 情绪 难受 上课 考试','先接住对方说的具体处境，再决定需不需要建议；不急着列一套步骤，不编造自己的类似经历。')]:
            self.save(scope,kind,scene,text,{'kind':'system_seed','basis':'主人在本会话要求降低模板腔、自然分享；可在管理页更改或拒绝'},approved=True)
        with self.db() as db:db.execute('INSERT OR IGNORE INTO migrations VALUES(?)',(key,))
