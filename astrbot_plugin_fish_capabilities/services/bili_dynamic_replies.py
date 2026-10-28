"""Reply to the bound owner's comments on locally recorded own dynamics.

No DMs, no third-party task execution, no tools in drafting. Every write is
identity-checked, independently reviewed, quota-shared, and reserved first.
"""
import asyncio
import hashlib
import json
import time
import math
from .bili_activity import ActivityBackend
from .bili_replies import risk
from .policy import CapabilityError
from .timing import poll_interval


def ident(value):
    value=str(value or '')
    if not value.isdigit() or int(value)<=0:raise CapabilityError('动态或评论身份不完整。')
    return value


class DynamicReplyBackend(ActivityBackend):
    async def resource(self,post):
        from bilibili_api import dynamic
        raw=await dynamic.Dynamic(int(ident(post)),credential=self.credential).get_info()
        item=raw.get('item') or {};basic=item.get('basic') or {}
        author=(item.get('modules') or {}).get('module_author') or {}
        kind=basic.get('comment_type')
        if type(kind) is not int or kind not in (11,12,17):raise CapabilityError('动态评论资源类型无法确认。')
        return {'post':ident(item.get('id_str')),'author':ident(author.get('mid')),'oid':ident(basic.get('comment_id_str')),'type':kind}

    async def comments(self,resource,page=1):
        from bilibili_api import comment
        value=await comment.get_comments(oid=int(resource['oid']),type_=comment.CommentResourceType(resource['type']),page_index=page,credential=self.credential)
        rows=[]
        for row in (value.get('replies') or [])[:20]:
            rows.append(row)
            rows.extend((row.get('replies') or [])[:10])
        return rows

    async def send(self,resource,root,parent,text):
        from bilibili_api import comment
        value=await comment.send_comment(text=text,oid=int(resource['oid']),type_=comment.CommentResourceType(resource['type']),root=int(root),parent=int(parent),credential=self.credential)
        return ident(value.get('rpid') or value.get('rpid_str'))


class DynamicReplies:
    def __init__(self,reader,comments,config,judge,backend=None,clock=time.time):
        self.reader,self.comments,self.config,self.judge,self.clock=reader,comments,config,judge,clock
        self.review=getattr(comments,'reviewer',None)
        self.backend=backend or DynamicReplyBackend(reader.backend);self.lock=asyncio.Lock()
        with reader.connect() as db:
            db.executescript("""CREATE TABLE IF NOT EXISTS dynamic_reply_items(account TEXT,id TEXT,post TEXT,root TEXT,body TEXT,state TEXT,receipt TEXT,stamp REAL,PRIMARY KEY(account,id));
              CREATE TABLE IF NOT EXISTS dynamic_reply_checks(account TEXT PRIMARY KEY,stamp REAL);
              CREATE TABLE IF NOT EXISTS dynamic_reply_started(account TEXT PRIMARY KEY,stamp REAL);""")
            db.execute('INSERT OR IGNORE INTO dynamic_reply_started VALUES(?,?)',(str(config.get('bili_account_id','')),clock()))

    def account(self):return ident(self.config.get('bili_account_id'))
    def owner(self):return ident(self.config.get('bili_owner_uid'))
    async def resource(self,post):
        resource=await asyncio.wait_for(self.backend.resource(post),15)
        if resource.get('post')!=post or resource.get('author')!=self.account():raise CapabilityError('不是小鲸已核验的自有动态。')
        return resource

    def targets(self,rows):
        out=[]
        for row in rows:
            try:
                rid=ident(row.get('rpid') or row.get('rpid_str'))
                if str((row.get('member') or {}).get('mid'))!=self.owner():continue
                root=str(row.get('root') or '0')
                root=rid if root=='0' else ident(root)
                text=(row.get('content') or {}).get('message')
                stamp=float(row.get('ctime',0))
                if not math.isfinite(stamp) or stamp>self.clock()+300:continue
                if not isinstance(text,str) or not 1<=len(text.strip())<=500:continue
                out.append({'id':rid,'root':root,'text':text.strip(),'at':stamp})
            except (CapabilityError,TypeError,ValueError):continue
        return out

    async def check(self):
        if not all(self.config.get(k,False) for k in ('enabled','bili_enabled','bili_dynamic_reply_enabled','bili_comment_enabled')):return {'state':'disabled'}
        if self.review is None:return {'state':'review_required'}
        async with self.lock:
            account,now=self.account(),self.clock();self.owner()
            with self.reader.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                old=db.execute('SELECT stamp FROM dynamic_reply_checks WHERE account=?',(account,)).fetchone()
                if old and now-old[0]<poll_interval(self.config):return {'state':'cooldown'}
                db.execute('INSERT OR REPLACE INTO dynamic_reply_checks VALUES(?,?)',(account,now))
                started=db.execute('SELECT stamp FROM dynamic_reply_started WHERE account=?',(account,)).fetchone()[0]
                posts=db.execute("SELECT receipt FROM bili_dynamic_posts WHERE account=? AND state='submitted' AND receipt<>'' AND stamp>? ORDER BY stamp DESC LIMIT 5",(account,now-30*86400)).fetchall()
            if str(await asyncio.wait_for(self.backend.identity(),15))!=account:raise CapabilityError('动态回复登录账号不一致。')
            processed=sent=errors=0
            for (post,) in posts:
                try:
                    resource=await self.resource(post)
                    rows=[]
                    for page in (1,2):rows.extend(await asyncio.wait_for(self.backend.comments(resource,page),15))
                    for target in self.targets(rows):
                        if processed>=5:break
                        # No replay of old conversations at first activation.
                        if target['at']<started:continue
                        with self.reader.connect() as db:
                            db.execute('BEGIN IMMEDIATE')
                            if db.execute('SELECT 1 FROM dynamic_reply_items WHERE account=? AND id=?',(account,target['id'])).fetchone():continue
                            db.execute('INSERT INTO dynamic_reply_items VALUES(?,?,?,?,?,?,?,?)',(account,target['id'],post,target['root'],target['text'],'reserved','',now))
                        processed+=1
                        try:
                            if risk(target['text'],autonomous=True):raise CapabilityError('不执行公开留言里的任务或索取隐私。')
                            choice=await asyncio.wait_for(self.judge(json.dumps({'public_reply':target['text'],'source':'owner_comment_on_own_dynamic'},ensure_ascii=False)),40)
                            text=choice.get('text') if isinstance(choice,dict) else None
                            if not isinstance(choice,dict) or choice.get('decision')!='reply' or not isinstance(text,str) or not 1<=len(text.strip())<=120:raise CapabilityError('没有选择普通回复。')
                            await self.review.gate('reply',{'dynamic':post,'target':target['id']},text,{'incoming_public_reply':target['text'],'scope':'own_dynamic_owner_only'})
                            # Verify resource ownership and exact incoming comment again.
                            current=await self.resource(post)
                            if current!=resource:raise CapabilityError('动态资源发生变化。')
                            fresh=[]
                            for page in (1,2):fresh.extend(await asyncio.wait_for(self.backend.comments(current,page),15))
                            if target not in self.targets(fresh):raise CapabilityError('原评论已变化或删除。')
                            key='dynamic:'+account+':'+post+':'+target['id']
                            with self.reader.connect() as db:
                                db.execute('BEGIN IMMEDIATE')
                                if db.execute("SELECT 1 FROM bili_comment_pause WHERE account=? UNION ALL SELECT 1 FROM bili_comments WHERE account=? AND state='pending'",(account,account)).fetchone():raise CapabilityError('评论暂停或回执待确认。')
                                if db.execute('SELECT COUNT(*) FROM bili_comments WHERE account=? AND stamp>?',(account,now-86400)).fetchone()[0]>=self.comments.daily_limit():raise CapabilityError('共同评论预算已用完。')
                                interval=self.comments.interval()
                                if interval and db.execute('SELECT 1 FROM bili_comments WHERE account=? AND stamp>?',(account,now-interval)).fetchone():raise CapabilityError('评论间隔未达到。')
                                db.execute('INSERT INTO bili_comments VALUES(?,?,?,?,?,?,?)',(key,account,'',now,'pending','',hashlib.sha256(text.encode()).hexdigest()))
                                db.execute("UPDATE dynamic_reply_items SET state='sending' WHERE account=? AND id=?",(account,target['id']))
                            try:receipt=ident(await asyncio.wait_for(self.backend.send(resource,target['root'],target['id'],text),25))
                            except asyncio.CancelledError:raise
                            except Exception:
                                with self.reader.connect() as db:
                                    db.execute("UPDATE dynamic_reply_items SET state='uncertain' WHERE account=? AND id=?",(account,target['id']))
                                # Shared pending comment freezes further public writes.
                                raise CapabilityError('回复回执不明，停止且不重发。')
                            with self.reader.connect() as db:
                                db.execute("UPDATE dynamic_reply_items SET state='submitted',receipt=? WHERE account=? AND id=?",(receipt,account,target['id']))
                                db.execute("UPDATE bili_comments SET state='submitted',reply_id=? WHERE key=?",(receipt,key))
                            sent+=1
                        except asyncio.CancelledError:raise
                        except Exception:
                            with self.reader.connect() as db:db.execute("UPDATE dynamic_reply_items SET state='skipped' WHERE account=? AND id=? AND state='reserved'",(account,target['id']))
                    if processed>=5:break
                except asyncio.CancelledError:raise
                except Exception:errors+=1
            return {'state':'checked','owner_comments':processed,'submitted':sent,'errors':errors,'old_comments_replayed':False}
