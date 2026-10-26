"""Owner-authorized video comments with durable reservations; no retry on uncertainty."""
from __future__ import annotations
import asyncio
import hashlib
import html
import json
import re
import time
from .policy import CapabilityError,bounded_int
from .http import PublicJSON


OWNER_MARKER = '{{owner}}'


def comment_text_matches(received, *, text=None, digest=None):
    """Legacy reply reads HTML-escape text; preserve exact and literal-entity cases."""
    if not isinstance(received,str):return False
    candidates=(received,html.unescape(received))
    if text is not None:return any(value==text for value in candidates)
    return isinstance(digest,str) and any(hashlib.sha256(value.encode()).hexdigest()==digest for value in candidates)


def render_owner_mention(text, name):
    """Insert only the verified nickname. Legacy callers may omit the marker."""
    if OWNER_MARKER not in text:
        return text+' @'+name
    before, after = text.split(OWNER_MARKER)
    left = '' if not before or before[-1].isspace() else ' '
    right = '' if not after or after[0].isspace() else ' '
    return (before+left+'@'+name+right+after).strip()


class CommentBackend:
    def __init__(self, reader_backend):
        self.backend = reader_backend

    async def identity(self):
        from .bili_account import verify_account
        credential = self.backend.credential()
        if credential is None:
            raise CapabilityError('尚未登录 B站，请主人在平板本地扫码。')
        credential.raise_for_no_sessdata()
        credential.raise_for_no_bili_jct()
        info = await asyncio.to_thread(verify_account,{k:str(getattr(credential,k,'') or '') for k in ('sessdata','bili_jct','dedeuserid','buvid3')})
        return str(info['mid'])

    async def send(self, video_id, text, mention=None, meme=None):
        from bilibili_api import comment
        credential = self.backend.credential()
        info = await self.backend.info(video_id)
        aid = int(info['aid'])
        pictures=None
        if meme:
            from bilibili_api.utils.picture import Picture
            pictures=Picture.from_file(str(meme.path))
        if mention:
            from bilibili_api.utils.network import Api
            api=comment.API['comment']['send']
            if api.get('url')!='https://api.bilibili.com/x/v2/reply/add' or api.get('method')!='POST':raise CapabilityError('评论接口发生变化，未发布。')
            image_fields={}
            if pictures:
                uploaded=await comment.upload_image(image=pictures,credential=credential)
                image_fields['pictures']=json.dumps([{'img_src':uploaded['image_url'],'img_width':uploaded['image_width'],'img_height':uploaded['image_height'],'img_size':uploaded['img_size']}])
            result=await Api(**api,credential=credential).update_data(**image_fields,oid=aid,type=1,message=text,plat=1,
                gaia_source='main_web',statistics=json.dumps({'appId':100,'platform':5}),
                at_name_to_mid=json.dumps({mention['name']:int(mention['uid'])},ensure_ascii=False)).result
        else:
            options={'pic':pictures} if pictures else {}
            result = await comment.send_comment(text=text, oid=aid,
                type_=comment.CommentResourceType.VIDEO, credential=credential,**options)
        reply_id = str(result.get('rpid') or result.get('rpid_str') or (result.get('reply') or {}).get('rpid') or '')
        return {'reply_id': reply_id, 'aid': aid,'mention_submitted':bool(mention),'notification_received_verified':False}

    async def verify(self, aid, reply_id, account, text):
        from bilibili_api import comment
        result = await comment.get_comments(oid=aid, type_=comment.CommentResourceType.VIDEO,
            order=comment.OrderType.TIME, page_index=1, credential=self.backend.credential())
        return any(str(row.get('rpid')) == reply_id and str((row.get('member') or {}).get('mid')) == account
            and comment_text_matches((row.get('content') or {}).get('message'),text=text) for row in result.get('replies') or [])

    async def prepare_mention(self,owner_uid):
        from bilibili_api import user
        from .bili_social import uid
        owner_uid=uid(owner_uid)
        info=await user.User(int(owner_uid)).get_user_info()
        name=str(info.get('name') or '').strip()
        if str(info.get('mid'))!=owner_uid or not name or len(name)>60 or re.search(r'[@＠\r\n]',name):raise CapabilityError('主人B站身份暂未核实，未发布带@评论。')
        return {'uid':owner_uid,'name':name}

    async def verify_public(self,aid,reply_id,account,text):
        # Explicitly anonymous: no SDK credential, Cookie, or automatic login.
        for page in (1,2):
            value=await PublicJSON().get('https://api.bilibili.com/x/v2/reply?type=1&oid='+str(int(aid))+'&sort=0&pn='+str(page),{'api.bilibili.com'})
            if value.get('code')!=0:return None
            data=value.get('data') or {};rows=list(data.get('replies') or [])+list(data.get('top_replies') or [])
            for row in rows:
                if str(row.get('rpid'))==str(reply_id) and str((row.get('member') or {}).get('mid'))==str(account) and comment_text_matches((row.get('content') or {}).get('message'),text=text):return True
            if not data.get('replies'):break
        return False


class BiliComments:
    def __init__(self, reader, settings, backend=None, clock=time.time):
        self.reader, self.settings, self.clock = reader, settings, clock
        self.backend = backend or CommentBackend(reader.backend)
        self.reviewer = None
        self.media = None
        with reader.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS bili_comment_pause(account TEXT PRIMARY KEY,reason TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS bili_comments(key TEXT PRIMARY KEY, account TEXT, bvid TEXT, stamp REAL, state TEXT, reply_id TEXT, text_hash TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS bili_visibility_meta(version INTEGER PRIMARY KEY)')
            if not db.execute('SELECT 1 FROM bili_visibility_meta WHERE version=2').fetchone():
                db.execute("UPDATE bili_comments SET state='legacy_author_visible' WHERE state='visible'")
                db.execute('INSERT INTO bili_visibility_meta VALUES(2)')

    def interval(self):
        return bounded_int(self.settings.get('bili_comment_interval_seconds',1800),0,86400,'评论间隔秒数')

    def daily_limit(self):
        return bounded_int(self.settings.get('bili_comment_daily_limit',2),1,20,'滚动24小时评论上限')

    def status(self):
        account = str(self.settings.get('bili_account_id', ''))
        with self.reader.connect() as db:
            paused = db.execute('SELECT reason FROM bili_comment_pause WHERE account=?', (account,)).fetchone()
            rows = db.execute('SELECT state,COUNT(*) FROM bili_comments WHERE account=? GROUP BY state', (account,)).fetchall()
        return {'comments_enabled': bool(self.settings.get('bili_comment_enabled', False)),
            'account_configured': bool(account), 'paused': bool(paused),
            'comment_interval_seconds':self.interval(),'daily_comment_limit':self.daily_limit(),
            'pause_reason': paused[0] if paused else None, 'receipts': dict(rows),
            'owner_mention_enabled':bool(self.settings.get('bili_owner_mention_enabled',False)),'owner_bound':bool(self.settings.get('bili_owner_uid')),
            'instruction': '不自动解除暂停；由主人在本地核对账号、验证与回执后处理。'}

    async def post(self, reading_id, text, evidence_ids, mention_owner=False,meme_id='',meme_sha256=''):
        original_text=text
        if not self.settings.get('bili_comment_enabled', False):
            raise CapabilityError('B站评论尚未启用；搜索、阅读与推荐可独立使用。')
        account = str(self.settings.get('bili_account_id', ''))
        if not account.isdigit():
            raise CapabilityError('请先由主人在本地绑定要使用的 B站账号。')
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 220:
            raise CapabilityError('评论需要 1～220 字。')
        text = text.strip()
        if type(mention_owner) is not bool:raise CapabilityError('mention_owner必须是布尔值。')
        markers=text.count(OWNER_MARKER)
        if markers>1 or (markers and not mention_owner):
            raise CapabilityError('只在决定@主人时放一个{{owner}}占位符；不@就不要占位符。')
        if '@' in text or '＠' in text:raise CapabilityError('不要手写@；只能通过mention_owner提及已绑定的主人一次。')
        if re.search(r'https?://|SESSDATA|bili_jct|sk-[A-Za-z0-9]{10,}|\b1[3-9]\d{9}\b', text, re.I):
            raise CapabilityError('公开评论不能包含凭据、手机号或外部链接。')
        if not isinstance(evidence_ids, list) or not 1 <= len(evidence_ids) <= 8 or not all(isinstance(x,str) for x in evidence_ids):
            raise CapabilityError('评论必须引用实际读取过、与观点相关的来源依据。')
        image=None
        if self.media:
            await self.media.validate(text)
        if meme_id:
            if not self.media or not self.reviewer:raise CapabilityError('图片评论需要图库验证及独立审核。')
            image=self.media.image(meme_id)
            if meme_sha256 and image.sha256!=meme_sha256:raise CapabilityError('批准后图片已改变，未发送。')
        now = self.clock()
        with self.reader.connect() as db:
            row = db.execute('SELECT packet,stamp FROM readings WHERE id=?', (reading_id,)).fetchone()
        if not row or row[1] < now - 86400:
            raise CapabilityError('阅读凭据不存在或超过一天，请重新阅读。')
        packet = json.loads(row[0])
        if not 0<float(packet.get('duration',0))<=600:raise CapabilityError('只允许基于不超过10分钟视频的有效阅读凭据评论。')
        if not set(evidence_ids) <= {r['evidence_id'] for r in packet['evidence']}:
            raise CapabilityError('不能基于未读过的内容发表评论。')
        video_id = packet['bvid']
        key = hashlib.sha256((account + ':' + video_id).encode()).hexdigest()
        try:
            identity = await asyncio.wait_for(self.backend.identity(), 15)
        except Exception:
            raise CapabilityError('B站登录状态检查失败；未发布评论。') from None
        if identity != account:
            raise CapabilityError('登录账号与主人绑定的账号不一致；未发布。')
        mention=None
        if mention_owner:
            owner=str(self.settings.get('bili_owner_uid',''))
            if not self.settings.get('bili_owner_mention_enabled',False) or not owner.isdigit() or int(owner)<=0 or owner==account:raise CapabilityError('主人@开关或准确身份尚未配置，未发布。')
            try:mention=await asyncio.wait_for(self.backend.prepare_mention(owner),15)
            except Exception:raise CapabilityError('无法核验主人B站身份，本次没有发布。') from None
            if str(mention.get('uid'))!=owner or not isinstance(mention.get('name'),str) or not mention['name'].strip() or re.search(r'[@＠\r\n]',mention['name']):raise CapabilityError('主人@映射不合法，未发布。')
            text=render_owner_mention(text,mention['name'])
            if len(text)>220:raise CapabilityError('加上@主人后超过220字，请缩短正文。')
        if self.reviewer:
            payload={'reading_id':reading_id,'text':original_text,'evidence_ids':evidence_ids,'mention_owner':mention_owner}
            public={'bvid':video_id,'title':packet.get('title'),'evidence':[e for e in packet.get('evidence',[]) if e['evidence_id'] in evidence_ids],'source_inventory':packet.get('source_inventory',[]),'limitation':'只据所列来源审核，不将抽样画面称为完整观看，不将歌词覆盖率当作主题相关性'}
            if image:
                payload.update(meme_id=meme_id,meme_sha256=image.sha256)
                public.update(_image_path=str(image.path),image_description=image.description,image_text=image.image_text)
            await self.reviewer.gate('root',payload,text,public)
        with self.reader.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM bili_comment_pause WHERE account=?', (account,)).fetchone():
                raise CapabilityError('评论已暂停，需要主人检查后在本地恢复。')
            if db.execute("SELECT 1 FROM bili_comments WHERE account=? AND state='pending'", (account,)).fetchone():
                raise CapabilityError('存在结果未确认的评论，不会继续发布。')
            if db.execute('SELECT 1 FROM bili_comments WHERE key=?', (key,)).fetchone():
                raise CapabilityError('此账号已尝试评论该视频，不重复发布。')
            limit=self.daily_limit()
            if db.execute('SELECT COUNT(*) FROM bili_comments WHERE account=? AND stamp>?',(account,now-86400)).fetchone()[0]>=limit:
                raise CapabilityError('评论预算已达上限：滚动24小时最多'+str(limit)+'条。')
            interval=self.interval()
            if interval>0 and db.execute('SELECT 1 FROM bili_comments WHERE account=? AND stamp>?',(account,now-interval)).fetchone():
                raise CapabilityError('评论间隔尚未达到当前配置的'+str(interval)+'秒。')
            db.execute('INSERT INTO bili_comments VALUES(?,?,?,?,?,?,?)', (key, account, video_id, now, 'pending', '', hashlib.sha256(text.encode()).hexdigest()))
        try:
            if image:
                self.media.library.bytes_for(image)
                request=self.backend.send(video_id,text,mention=mention,meme=image)
            else:request=self.backend.send(video_id,text,mention=mention) if mention else self.backend.send(video_id,text)
            result = await asyncio.wait_for(request,35 if image else 20)
            reply_id = str(result.get('reply_id') or '')
            if not reply_id.isdigit() or int(reply_id) <= 0:
                raise ValueError('missing_receipt')
        except Exception:
            with self.reader.connect() as db:
                db.execute('UPDATE bili_comments SET state=? WHERE key=?', ('uncertain', key))
                db.execute('INSERT OR REPLACE INTO bili_comment_pause VALUES(?,?)', (account, '发布失败或结果不确定；需人工检查，禁止自动补发'))
            raise CapabilityError('评论发布失败或结果不确定，已暂停后续发布；请勿自动重试。') from None
        with self.reader.connect() as db:
            db.execute('UPDATE bili_comments SET state=?,reply_id=? WHERE key=?', ('submitted', reply_id, key))
        author_visible=False;visible=None
        try:author_visible=await asyncio.wait_for(self.backend.verify(result['aid'],reply_id,account,text),12)
        except Exception:pass
        public_check=getattr(self.backend,'verify_public',None)
        if public_check:
            try:visible=await asyncio.wait_for(public_check(result['aid'],reply_id,account,text),15)
            except Exception:pass
        state='visible' if visible is True else ('author_visible' if author_visible else 'submitted')
        with self.reader.connect() as db:db.execute('UPDATE bili_comments SET state=? WHERE key=?',(state,key))
        if getattr(self,'timeline',None):self.timeline.add('bili_comment',account+':'+reply_id,text,state=state,details={'bvid':video_id,'reply_id':reply_id,'publicly_visible':visible is True})
        return {'submitted':True,'author_visible_verified':bool(author_visible),'publicly_visible_verified':visible is True,
            'visibility_status':'anonymous_read_verified' if visible is True else ('author_read_only' if author_visible else 'unconfirmed'),
            'mention_submitted':bool(mention),'notification_received_verified':False,'reply_id':reply_id,
            'url':packet['url']+'#reply'+reply_id,
            'instruction':'回执、发帖账号可见、匿名视角可见是不同状态。只有匿名回读匹配才能称本次公开可见，不保证所有地区或长期可见；无法证明主人收到通知。未确认时不要补发、换方式发或声称已经通知到主人。'}
