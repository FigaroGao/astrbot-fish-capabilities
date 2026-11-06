"""Private, sourced and revisable notes. Impressions are never owner facts."""
import json,re,sqlite3,time
from contextlib import contextmanager
from pathlib import Path
from .policy import CapabilityError

KINDS={'correction','knowledge_gap','impression','personal_note'}
def clean(value,limit):
    if not isinstance(value,str) or not value.strip() or len(value)>limit:raise CapabilityError('笔记内容为空或过长。')
    if re.search(r'(?i)sk-[a-z0-9_-]{12,}|(?:api.?key|token|password|SESSDATA)\s*[:=]',value):raise CapabilityError('不将凭据写进笔记。')
    return value.strip()

class OwnerNotebook:
    def __init__(self,path,clock=time.time):
        self.path=Path(path);self.clock=clock
        with self.db() as db:db.execute('CREATE TABLE IF NOT EXISTS notes(id INTEGER PRIMARY KEY,kind TEXT,topic TEXT,content TEXT,evidence TEXT,source TEXT,stamp REAL,active INTEGER,previous INTEGER)')
        with self.db() as db:
            db.executescript("""CREATE TABLE IF NOT EXISTS study(id INTEGER PRIMARY KEY,scope TEXT,topic TEXT,body TEXT,source TEXT,state TEXT,rev INTEGER,updated REAL,retry REAL DEFAULT 0,UNIQUE(scope,topic));
            CREATE TABLE IF NOT EXISTS study_versions(id INTEGER,body TEXT,source TEXT,state TEXT,rev INTEGER,PRIMARY KEY(id,rev));""")
        self.path.chmod(0o600)
    @contextmanager
    def db(self):
        db=sqlite3.connect(self.path,timeout=5)
        try:
            with db:yield db
        finally:db.close()
    def save(self,kind,topic,content,evidence,available_source,previous=0):
        if kind not in KINDS:raise CapabilityError('笔记类型不支持。')
        topic=clean(topic,80);content=clean(content,800);evidence=clean(evidence,400)
        if len(evidence)<4 or evidence not in available_source:raise CapabilityError('需引用本轮或已取得资料中的真实依据，不猜测补写。')
        if type(previous)is not int or previous<0:raise CapabilityError('旧笔记编号无效。')
        with self.db() as db:
            if previous:
                old=db.execute('SELECT kind FROM notes WHERE id=? AND active=1',(previous,)).fetchone()
                if not old or old[0]!=kind:raise CapabilityError('旧笔记不存在、已被替代或类型不一致。')
            duplicate=db.execute('SELECT id FROM notes WHERE active=1 AND kind=? AND topic=? AND content=?',(kind,topic,content)).fetchone()
            if duplicate:return {'saved':True,'id':duplicate[0],'duplicate':True}
            if previous:db.execute('UPDATE notes SET active=0 WHERE id=?',(previous,))
            ident=db.execute('INSERT INTO notes(kind,topic,content,evidence,source,stamp,active,previous) VALUES(?,?,?,?,?,?,1,?)',
                (kind,topic,content,evidence,'subjective_inference' if kind=='impression' else 'source_quote',self.clock(),previous or None)).lastrowid
        return {'saved':True,'id':ident,'subjective':kind=='impression','private_only':True}
    def search(self,query='',kind='',limit=6):
        if not isinstance(query,str) or len(query)>200 or type(limit)is not int or not 1<=limit<=12:raise CapabilityError('查询参数无效。')
        if kind and kind not in KINDS:raise CapabilityError('笔记类型不支持。')
        with self.db() as db:
            rows=db.execute('SELECT id,kind,topic,content,evidence,source,stamp,previous FROM notes WHERE active=1 AND (?="" OR kind=?) AND (?="" OR instr(topic,?)>0 OR instr(content,?)>0) ORDER BY stamp DESC LIMIT ?',
                (kind,kind,query,query,query,limit)).fetchall()
        keys=['id','kind','topic','content','evidence','source','at','previous']
        return {'notes':[dict(zip(keys,r)) for r in rows],'instruction':'仅原主人私聊。impression是小鲸当时的主观看法，可变可错，不是诊断或确定事实；更正保留历史。不得写入群或公开评论。'}
    def archive(self,ident):
        with self.db() as db:db.execute('UPDATE notes SET active=0 WHERE id=?',(ident,))
        return {'archived':True}

    def study_rows(self,scope):
        with self.db() as db:
            rows=db.execute('SELECT id,topic,body,source,state,rev,updated,retry FROM study WHERE scope=? ORDER BY updated DESC LIMIT 300',(scope,)).fetchall()
        return [dict(id=i,topic=t,body=b,source=json.loads(s),state=status,revision=r,updated=u,retry_at=retry,needs_recheck=status=='provisional' and self.clock()-u>=7*86400 and bool(re.search(r'版本|最新|目前|当前|赛季|赛事|价格|今年|本周',t+b))) for i,t,b,s,status,r,u,retry in rows]

    def related(self,scope,message):
        from .companion_learning import terms
        clues=terms(message)
        ranked=[]
        for row in self.study_rows(scope):
            matched=clues & terms(row['topic'])
            if len(matched)>=2 or (len(row['topic'])>=2 and row['topic'] in message):
                ranked.append((len(matched),row))
        return [row for _,row in sorted(ranked,key=lambda pair:-pair[0])[:2]]

    def study_save(self,scope,topic,body,source,state,ident=0,revision=0):
        topic=clean(topic,80);body=clean(body,600)
        if not scope or state not in ('question','noted','provisional','corrected'):raise CapabilityError('学习笔记范围或状态无效。')
        encoded=json.dumps(source,ensure_ascii=False)
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            if ident:
                old=db.execute('SELECT body,source,state,rev FROM study WHERE id=? AND scope=?',(ident,scope)).fetchone()
                if not old or old[3]!=revision:raise CapabilityError('笔记版本已变化，请重新读取。')
                db.execute('INSERT INTO study_versions VALUES(?,?,?,?,?)',(ident,*old))
                db.execute('UPDATE study SET body=?,source=?,state=?,rev=rev+1,updated=? WHERE id=?',(body,encoded,state,self.clock(),ident))
            else:
                old=db.execute('SELECT id FROM study WHERE scope=? AND topic=?',(scope,topic)).fetchone()
                if old:return {'id':old[0],'duplicate':True}
                ident=db.execute('INSERT INTO study(scope,topic,body,source,state,rev,updated) VALUES(?,?,?,?,?,1,?)',(scope,topic,body,encoded,state,self.clock())).lastrowid
        return {'id':ident,'revision':revision+1,'state':state}

    def claim_question(self,scope,ident):
        now=self.clock()
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute("SELECT topic,rev,state,updated,body FROM study WHERE scope=? AND id=? AND state IN ('question','provisional') AND retry<=?",(scope,ident,now)).fetchone()
            if not row:return None
            if row[2]=='provisional' and (now-row[3]<7*86400 or not re.search(r'版本|最新|目前|当前|赛季|赛事|价格|今年|本周',row[0]+row[4])):return None
            db.execute('UPDATE study SET retry=? WHERE id=?',(now+86400,ident))
        return row
