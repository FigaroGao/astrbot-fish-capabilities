"""Scoped LivingMemory adapter with version checks and reversible audit copies."""
import asyncio
import hashlib
import json
import sqlite3
import time
from .policy import CapabilityError
from .memory_provenance import correction_provenance, injection_label


def metadata(row):
    value=row.get('metadata') or {}
    return json.loads(value) if isinstance(value,str) else dict(value)


class MemoryEditor:
    def __init__(self,path,review=None):
        self.path=path;self.lock=asyncio.Lock();self.review=review
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS edits(id INTEGER PRIMARY KEY,stamp REAL,old_id INTEGER,new_id INTEGER,scope TEXT,persona TEXT,before TEXT,after TEXT,reason TEXT,state TEXT)')
        path.chmod(0o600)

    def scoped(self,row,scope,persona):
        m=metadata(row)
        if m.get('session_id')!=scope or m.get('persona_id')!=persona:
            raise CapabilityError('这条记忆不属于当前会话与人格，不读取或修改。')
        return m

    async def search(self,engine,scope,persona,query):
        if not isinstance(query,str) or not 1<=len(query.strip())<=160:
            raise CapabilityError('请提供1至160字的检索关键词。')
        rows=await engine.search_memories(query,k=5,session_id=scope,persona_id=persona)
        out=[]
        for r in rows:
            ident=int(r.doc_id)
            record=await engine.get_memory_record(ident)
            if not record:continue
            try:m=self.scoped(record,scope,persona)
            except CapabilityError:continue
            text=str(record.get('text') or '')
            out.append(dict(id=ident,content=text[:2500],version=hashlib.sha256(text.encode()).hexdigest(),
                            provenance=m.get('fish_provenance',{}),
                            temporal_label=injection_label(m,now=time.time()) or '已失效，仅供核对和更正'))
        return {'memories':out,'instruction':'只检索当前会话与人格。旧记忆是历史材料，不是当前状态；纠错需要版本号、明确更正原因及主人当前消息中的依据，不凭空改事实。不改变人格、权限或跨会话隐私。'}

    async def correct(self,engine,scope,persona,ident,version,content,reason,evidence,current_message):
        if type(ident)is not int or not 1<=len(content.strip())<=2500 or not 3<=len(reason.strip())<=300:
            raise CapabilityError('需要真实条目ID、完整修正内容和具体原因。')
        if not isinstance(evidence,str) or len(evidence.strip())<4:
            raise CapabilityError('更正需要明确依据；不确定时先自然询问主人。')
        async with self.lock:
            row=await engine.get_memory_record(ident)
            if not row:raise CapabilityError('原记忆已不存在，请重新检索。')
            m=self.scoped(row,scope,persona);old=str(row.get('text') or '')
            if hashlib.sha256(old.encode()).hexdigest()!=version:
                raise CapabilityError('记忆已经变化，请重新检索后再修改。')
            historical=evidence not in current_message
            if historical and (not self.review or evidence not in old):
                raise CapabilityError('须引用主人当前明确更正，或仅将旧条目有日期的临时状态改写为历史；不能凭空添加新事实。')
            if self.review and not await self.review(dict(before=row,after=content,reason=reason,evidence=evidence,
                                                         owner_message=current_message[:1200],historical_only=historical)):
                raise CapabilityError('纠错依据不充分，原记忆未改；请先自然询问主人。')
            source=await engine.get_memory_source(ident)
            with sqlite3.connect(self.path) as db:
                cur=db.execute('INSERT INTO edits(stamp,old_id,scope,persona,before,after,reason,state) VALUES(?,?,?,?,?,?,?,?)',
                    (time.time(),ident,scope,persona,json.dumps(dict(record=row,sources=source),ensure_ascii=False),content,reason,'reserved'))
                audit=cur.lastrowid
            self.path.chmod(0o600)
            # Derived summaries and atoms must not retain the superseded facts.
            m.update(canonical_summary=content,persona_summary=content,key_facts=[content],correction_reason=reason,
                     fish_correction_audit=audit,updated_at=time.time())
            m=correction_provenance(m,ident=ident,evidence=evidence,observed_at=time.time(),historical=historical)
            try:
                new_id=await engine.replace_memory(ident,content=content,metadata=m,importance=float(m.get('importance',0.5)))
                state='completed'
            except Exception:
                with sqlite3.connect(self.path) as db:db.execute('UPDATE edits SET state=? WHERE id=?',('failed',audit))
                raise
            with sqlite3.connect(self.path) as db:db.execute('UPDATE edits SET new_id=?,state=? WHERE id=?',(new_id,state,audit))
            return {'corrected':True,'old_id':ident,'new_id':new_id,'audit_id':audit,'indices_rebuilt':True}
