"""Add-only likes/favorites on the bound bot account, with durable receipts."""
import asyncio
import json
import time

from .bilibili import bvid
from .bili_comments import CommentBackend
from .policy import CapabilityError, bounded_int


class ActionBackend:
    def __init__(self, backend):
        self.backend = backend
        self.credential = None

    async def identity(self):
        # Freeze credentials for this operation; a concurrent local QR refresh
        # cannot switch the account between identity verification and mutation.
        credential = self.backend.credential()
        class Frozen:
            def credential(self): return credential
        account = await CommentBackend(Frozen()).identity()
        self.credential = credential
        return account

    def video(self, video_id):
        from bilibili_api import video
        return video.Video(bvid=video_id, credential=self.credential)

    async def check(self, kind, video_id, account, folder):
        v = self.video(video_id)
        if kind == 'like':
            result = await v.has_liked()
            if type(result) not in (bool, int) or result not in (0, 1):
                raise CapabilityError('点赞状态无法确认。')
            return bool(result)
        from bilibili_api import favorite_list
        value = await favorite_list.get_video_favorite_list(int(account), video=v, credential=self.credential)
        rows = value.get('list')
        if not isinstance(rows, list):
            raise CapabilityError('收藏夹列表无法确认。')
        row = next((x for x in rows if str(x.get('id')) == folder), None)
        if row is None or str(row.get('mid')) != account:
            raise CapabilityError('专用收藏夹不属于当前绑定账号，未操作。')
        state = row.get('fav_state')
        if type(state) not in (bool, int) or state not in (0, 1):
            raise CapabilityError('专用收藏夹内的视频状态无法确认。')
        return bool(state)

    async def send(self, kind, video_id, folder):
        v = self.video(video_id)
        if kind == 'like':
            await v.like(status=True)
        else:
            # Never remove from other folders, unlike, coin, or triple.
            await v.set_favorite(add_media_ids=[int(folder)], del_media_ids=[])


class BiliActions:
    def __init__(self, reader, config, backend=None, clock=time.time):
        self.reader, self.config, self.clock = reader, config, clock
        self.backend = backend or ActionBackend(reader.backend)
        self.lock = asyncio.Lock()
        with reader.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS bili_actions(account TEXT, kind TEXT, video TEXT, folder TEXT, stamp REAL, state TEXT, PRIMARY KEY(account,kind,video,folder))')

    def status(self):
        account = str(self.config.get('bili_account_id', ''))
        with self.reader.connect() as db:
            rows = db.execute('SELECT kind,COUNT(*) FROM bili_actions WHERE account=? AND stamp>? GROUP BY kind', (account, self.clock()-86400)).fetchall()
        return {'like_enabled': bool(self.config.get('bili_like_enabled', False)),
                'favorite_enabled': bool(self.config.get('bili_favorite_enabled', False)),
                'favorite_folder_configured': bool(self.config.get('bili_favorite_folder_id')),
                'limit_per_kind_24h': self.limit(), 'attempts_24h': dict(rows)}

    def limit(self):
        return bounded_int(self.config.get('bili_action_daily_limit', 20), 1, 100, '每种互动滚动24小时上限')

    async def apply(self, reading_id, kind):
        if kind not in ('like', 'favorite'):
            raise CapabilityError('只支持 like 点赞或 favorite 收藏，不提供取消、投币或一键三连。')
        if not self.config.get('enabled', False) or not self.config.get('bili_enabled', False) or not self.config.get('bili_'+kind+'_enabled', False):
            raise CapabilityError('这项B站互动尚未启用。')
        account = str(self.config.get('bili_account_id', ''))
        if not account.isdigit() or int(account) <= 0:
            raise CapabilityError('请先由主人绑定小鲸自己的B站账号。')
        folder = str(self.config.get('bili_favorite_folder_id', '')) if kind == 'favorite' else ''
        if kind == 'favorite' and (not folder.isdigit() or int(folder) <= 0):
            raise CapabilityError('请先由主人配置小鲸账号的专用收藏夹。')
        with self.reader.connect() as db:
            row = db.execute('SELECT packet,stamp FROM readings WHERE id=?', (reading_id,)).fetchone()
        if row is None or row[1] < self.clock()-86400:
            raise CapabilityError('请先实际读取视频，使用一天内的阅读凭据。')
        packet = json.loads(row[0])
        video_id = bvid(packet['bvid'])
        if not 0 < float(packet.get('duration', 0)) <= 600:
            raise CapabilityError('只互动已读取的不超过10分钟的视频。')
        key = (account, kind, video_id, folder)
        async with self.lock:
            try:
                if str(await asyncio.wait_for(self.backend.identity(), 15)) != account:
                    raise CapabilityError('登录账号与绑定账号不一致，未操作。')
                present = await asyncio.wait_for(self.backend.check(kind, video_id, account, folder), 15)
            except CapabilityError:
                raise
            except Exception:
                raise CapabilityError('账号或互动状态检查失败，未提交。') from None
            if type(present) is not bool:
                raise CapabilityError('互动状态未知，未提交。')
            if present:
                with self.reader.connect() as db:
                    db.execute("UPDATE bili_actions SET state='verified' WHERE account=? AND kind=? AND video=? AND folder=?", key)
                return self.receipt(kind, video_id, 'already_done', True, False)
            with self.reader.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                previous = db.execute('SELECT state FROM bili_actions WHERE account=? AND kind=? AND video=? AND folder=?', key).fetchone()
                if previous:
                    # A read-only reconciliation is allowed; never repeat POST
                    # after a timeout, reload, cancellation, or user-side undo.
                    return self.receipt(kind, video_id, 'not_confirmed_no_retry', False, False)
                count = db.execute('SELECT COUNT(*) FROM bili_actions WHERE account=? AND kind=? AND stamp>?', (account, kind, self.clock()-86400)).fetchone()[0]
                if count >= self.limit():
                    raise CapabilityError('本类互动的滚动24小时预算已用完。')
                db.execute('INSERT INTO bili_actions VALUES(?,?,?,?,?,?)', (*key, self.clock(), 'pending'))
            state, confirmed = 'uncertain', False
            try:
                await asyncio.wait_for(self.backend.send(kind, video_id, folder), 15)
                # Successful POST is not proof that the read state has changed.
                confirmed = await asyncio.wait_for(self.backend.check(kind, video_id, account, folder), 15) is True
                state = 'verified' if confirmed else 'submitted_unverified'
            except Exception:
                pass  # No exception text, transport details, or credential logs.
            with self.reader.connect() as db:
                db.execute('UPDATE bili_actions SET state=? WHERE account=? AND kind=? AND video=? AND folder=?', (state, *key))
            return self.receipt(kind, video_id, state, confirmed, True)

    @staticmethod
    def receipt(kind, video_id, state, confirmed, attempted):
        return {'action': kind, 'bvid': video_id, 'state': state, 'confirmed': confirmed,
                'write_attempted': attempted, 'instruction': '只有confirmed=true才说已经点赞/收藏；其他状态说明尚未确认，不重复提交。只操作小鲸绑定账号，不涉及投币。'}
