"""Owner-authorized video comments with durable reservations; no retry on uncertainty."""
from __future__ import annotations
import asyncio
import hashlib
import json
import re
import time
from .policy import CapabilityError


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

    async def send(self, video_id, text):
        from bilibili_api import comment
        credential = self.backend.credential()
        info = await self.backend.info(video_id)
        aid = int(info['aid'])
        result = await comment.send_comment(text=text, oid=aid,
            type_=comment.CommentResourceType.VIDEO, credential=credential)
        reply_id = str(result.get('rpid') or result.get('rpid_str') or (result.get('reply') or {}).get('rpid') or '')
        return {'reply_id': reply_id, 'aid': aid}

    async def verify(self, aid, reply_id, account, text):
        from bilibili_api import comment
        result = await comment.get_comments(oid=aid, type_=comment.CommentResourceType.VIDEO,
            order=comment.OrderType.TIME, page_index=1, credential=self.backend.credential())
        return any(str(row.get('rpid')) == reply_id and str((row.get('member') or {}).get('mid')) == account
            and (row.get('content') or {}).get('message') == text for row in result.get('replies') or [])


class BiliComments:
    def __init__(self, reader, settings, backend=None, clock=time.time):
        self.reader, self.settings, self.clock = reader, settings, clock
        self.backend = backend or CommentBackend(reader.backend)
        with reader.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS bili_comment_pause(account TEXT PRIMARY KEY,reason TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS bili_comments(key TEXT PRIMARY KEY, account TEXT, bvid TEXT, stamp REAL, state TEXT, reply_id TEXT, text_hash TEXT)')

    def status(self):
        account = str(self.settings.get('bili_account_id', ''))
        with self.reader.connect() as db:
            paused = db.execute('SELECT reason FROM bili_comment_pause WHERE account=?', (account,)).fetchone()
            rows = db.execute('SELECT state,COUNT(*) FROM bili_comments WHERE account=? GROUP BY state', (account,)).fetchall()
        return {'comments_enabled': bool(self.settings.get('bili_comment_enabled', False)),
            'account_configured': bool(account), 'paused': bool(paused),
            'pause_reason': paused[0] if paused else None, 'receipts': dict(rows),
            'instruction': '不自动解除暂停；由主人在本地核对账号、验证与回执后处理。'}

    async def post(self, reading_id, text, evidence_ids):
        if not self.settings.get('bili_comment_enabled', False):
            raise CapabilityError('B站评论尚未启用；搜索、阅读与推荐可独立使用。')
        account = str(self.settings.get('bili_account_id', ''))
        if not account.isdigit():
            raise CapabilityError('请先由主人在本地绑定要使用的 B站账号。')
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 220:
            raise CapabilityError('评论需要 1～220 字。')
        text = text.strip()
        if re.search(r'https?://|SESSDATA|bili_jct|sk-[A-Za-z0-9]{10,}|\b1[3-9]\d{9}\b', text, re.I):
            raise CapabilityError('公开评论不能包含凭据、手机号或外部链接。')
        if not isinstance(evidence_ids, list) or not 1 <= len(evidence_ids) <= 8 or not all(isinstance(x,str) for x in evidence_ids):
            raise CapabilityError('评论必须引用实际读取过的字幕依据。')
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
        with self.reader.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM bili_comment_pause WHERE account=?', (account,)).fetchone():
                raise CapabilityError('评论已暂停，需要主人检查后在本地恢复。')
            if db.execute("SELECT 1 FROM bili_comments WHERE account=? AND state='pending'", (account,)).fetchone():
                raise CapabilityError('存在结果未确认的评论，不会继续发布。')
            if db.execute('SELECT 1 FROM bili_comments WHERE key=?', (key,)).fetchone():
                raise CapabilityError('此账号已尝试评论该视频，不重复发布。')
            if db.execute('SELECT COUNT(*) FROM bili_comments WHERE account=? AND stamp>?', (account, now-86400)).fetchone()[0] >= 2:
                raise CapabilityError('评论预算已达上限：滚动24小时最多2条。')
            if db.execute('SELECT 1 FROM bili_comments WHERE account=? AND stamp>?', (account, now-1800)).fetchone():
                raise CapabilityError('评论至少间隔30分钟。')
            db.execute('INSERT INTO bili_comments VALUES(?,?,?,?,?,?,?)', (key, account, video_id, now, 'pending', '', hashlib.sha256(text.encode()).hexdigest()))
        try:
            result = await asyncio.wait_for(self.backend.send(video_id, text), 20)
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
        visible = False
        try:
            visible = await asyncio.wait_for(self.backend.verify(result['aid'], reply_id, account, text), 12)
        except Exception:
            pass
        if visible:
            with self.reader.connect() as db:
                db.execute('UPDATE bili_comments SET state=? WHERE key=?', ('visible', key))
        return {'submitted': True, 'publicly_visible_verified': visible, 'reply_id': reply_id,
            'url': packet['url'] + '#reply' + reply_id,
            'instruction': '仅拿到回执不等于公开可见；可见性未确认时不要声称发送成功，也不要补发。'}
