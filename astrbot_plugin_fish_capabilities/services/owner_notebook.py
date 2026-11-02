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
