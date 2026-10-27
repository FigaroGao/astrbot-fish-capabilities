"""Incremental text-description embeddings for the already-reviewed meme pack."""
import asyncio
import hashlib
import json
import math
import sqlite3
import time
from .policy import CapabilityError
from .companion_learning import terms


def vector(raw):
    if not isinstance(raw,(list,tuple)) or not 1<=len(raw)<=8192:raise CapabilityError('向量格式无效。')
    values=[float(x) for x in raw]
    if not all(math.isfinite(x) for x in values):raise CapabilityError('向量含无效值。')
    length=math.sqrt(sum(x*x for x in values))
    if length<=0:raise CapabilityError('向量为空。')
    return [x/length for x in values]


class MemeSemantic:
    def __init__(self,path,library,provider):
        self.path,self.library,self.provider=path,library,provider
        self.lock=asyncio.Lock();self.cache={}
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS vectors(namespace TEXT,id TEXT,digest TEXT,vector TEXT,stamp REAL,PRIMARY KEY(namespace,id))')
        path.chmod(0o600)

    def current(self):
        namespace,provider=self.provider()
        if not namespace or provider is None or not callable(getattr(provider,'get_embedding',None)):
            raise CapabilityError('尚无可用向量提供商，可继续使用文本候选。')
        return str(namespace),provider

    @staticmethod
    def description(meme):
        return ' '.join([meme.category,meme.description,meme.image_text,meme.usage_notes,*meme.tags])[:1000]

    async def index(self,limit=30):
        if type(limit)is not int or not 1<=limit<=50:raise CapabilityError('每批索引1至50张。')
        if self.lock.locked():return {'state':'already_indexing'}
        namespace,provider=self.current();done=0;failed=0
        async with self.lock:
            for meme in self.library.catalog():
                text=self.description(meme);digest=hashlib.sha256((meme.sha256+text).encode()).hexdigest()
                with sqlite3.connect(self.path) as db:
                    old=db.execute('SELECT digest FROM vectors WHERE namespace=? AND id=?',(namespace,meme.id)).fetchone()
                if old and old[0]==digest:continue
                try:values=vector(await asyncio.wait_for(provider.get_embedding(text),20))
                except asyncio.CancelledError:raise
                except Exception:
                    failed+=1
                    break  # Don't spend the whole batch on an unavailable endpoint.
                with sqlite3.connect(self.path) as db:
                    db.execute('INSERT OR REPLACE INTO vectors VALUES(?,?,?,?,?)',(namespace,meme.id,digest,json.dumps(values),time.time()))
                done+=1
                if done>=limit:break
        self.path.chmod(0o600);self.cache.clear()
        return {'indexed_this_batch':done,'failed':failed,'status':self.status(),
            'instruction':'只嵌入已有人审描述，不重新调用视觉模型；未处理的可再点增量索引。'}

    def status(self):
        memes=self.library.catalog()
        try:namespace,_=self.current()
        except CapabilityError:return {'available':False,'approved_images':len(memes),'indexed_current':0}
        with sqlite3.connect(self.path) as db:
            rows=dict(db.execute('SELECT id,digest FROM vectors WHERE namespace=?',(namespace,)))
        count=sum(rows.get(m.id)==hashlib.sha256((m.sha256+self.description(m)).encode()).hexdigest() for m in memes)
        return {'available':True,'approved_images':len(memes),'indexed_current':count,'pending':len(memes)-count}

    async def search(self,query,limit=6):
        if not isinstance(query,str) or not 1<=len(query.strip())<=200 or type(limit)is not int or not 1<=limit<=12:
            raise CapabilityError('表情查询限1至200字、1至12张。')
        memes=self.library.catalog();wanted=terms(query);scores=[];mode='text'
        try:
            namespace,provider=self.current();key=(namespace,query)
            with sqlite3.connect(self.path) as db:
                stored={i:(d,json.loads(v)) for i,d,v in db.execute('SELECT id,digest,vector FROM vectors WHERE namespace=?',(namespace,))}
            if not any(stored.get(m.id,(None,None))[0]==hashlib.sha256((m.sha256+self.description(m)).encode()).hexdigest() for m in memes):
                raise CapabilityError('尚未建立当前图库索引，先用文字候选。')
            if key in self.cache and time.time()-self.cache[key][0]<300:q=self.cache[key][1]
            else:
                q=vector(await asyncio.wait_for(provider.get_embedding(query),15))
                if len(self.cache)>=32:self.cache.pop(next(iter(self.cache)))
                self.cache[key]=(time.time(),q)
            for meme in memes:
                text=self.description(meme);entry=stored.get(meme.id)
                if entry and entry[0]==hashlib.sha256((meme.sha256+text).encode()).hexdigest() and len(entry[1])==len(q):
                    scores.append((sum(a*b for a,b in zip(q,entry[1])),meme))
            if scores:mode='semantic'
        except asyncio.CancelledError:raise
        except Exception:pass
        if not scores:
            scores=[(len(wanted & terms(self.description(m))),m) for m in memes]
            scores=[r for r in scores if r[0]>0]
        scores.sort(key=lambda x:(-x[0],x[1].id))
        return {'mode':mode,'candidates':[{'id':m.id,'category':m.category,'description':m.description,
            'image_text':m.image_text,'usage_notes':m.usage_notes,'score':round(score,4)} for score,m in scores[:limit]],
            'instruction':'只提供候选，不自动发送；由你结合语境选择，仍受原发送频率和公开审核约束。'}
