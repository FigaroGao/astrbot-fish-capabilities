from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path


class CapabilityError(Exception):
    """A concise public error; transport failures must not include credentials."""


@dataclass(frozen=True)
class Actor:
    user_id: str
    platform_id: str
    private: bool
    admin: bool = False
    group_id: str = ''

    @property
    def conversation(self) -> str:
        kind = 'FriendMessage' if self.private else 'GroupMessage'
        return f'{self.platform_id}:{kind}:{self.user_id if self.private else self.group_id}'


def require_owner(actor: Actor, owners: list[str], *, private: bool = True) -> None:
    if actor.user_id not in owners or not actor.admin or (private and not actor.private):
        raise CapabilityError('此能力只允许已配置的主人在私聊中使用。')


def bounded_int(value: int, low: int, high: int, name: str) -> int:
    if type(value) is not int or not low <= value <= high:
        raise CapabilityError(f'{name} 必须是 {low}～{high} 的整数。')
    return value


def contained_file(root: Path, relative: str, *, suffixes: set[str]) -> Path:
    # Reject links before resolve, including links in parent components.
    root = root.resolve()
    candidate = Path(relative)
    if candidate.is_absolute() or '..' in candidate.parts:
        raise CapabilityError('资源路径必须位于指定资源目录内。')
    target = root / candidate
    for parent in [target, *target.parents]:
        if parent == root:
            break
        if parent.is_symlink():
            raise CapabilityError('资源不能使用符号链接。')
    target = target.resolve()
    if not target.is_relative_to(root) or not target.is_file() or target.suffix.lower() not in suffixes:
        raise CapabilityError('资源不存在或文件格式不支持。')
    return target


class Ledger:
    """Persistent, transaction-protected quotas; no message bodies or secrets."""

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS reservations (id INTEGER PRIMARY KEY, scope TEXT NOT NULL, kind TEXT NOT NULL, turn TEXT NOT NULL, stamp REAL NOT NULL, units INTEGER NOT NULL, asset TEXT NOT NULL)')
            db.execute('CREATE INDEX IF NOT EXISTS quota_scope_stamp ON reservations(scope, stamp)')
            db.execute('CREATE TABLE IF NOT EXISTS reply_turns(scope TEXT,turn TEXT,stamp REAL,PRIMARY KEY(scope,turn))')

    def note_reply(self,scope,turn):
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO reply_turns VALUES(?,?,?)',(scope,turn,time.time()))
            db.execute('DELETE FROM reply_turns WHERE stamp<?',(time.time()-86400*35,))

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.execute('PRAGMA busy_timeout=5000')
        try:
            with db:
                yield db
        finally:
            db.close()

    def reserve(self, scope: str, kind: str, turn: str, *, cooldown: float, hourly: int,
                units: int = 1, asset: str = '', asset_cooldown: float = 3600,
                now: float | None = None, min_reply_gap: int = 0, requested: bool = False) -> int:
        now = time.time() if now is None else now
        if not scope or not turn or units <= 0 or cooldown < 0 or hourly <= 0:
            raise CapabilityError('无效的配额参数。')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            # Media share the same per-turn and cooldown budget, irrespective of kind.
            if db.execute('SELECT 1 FROM reservations WHERE scope=? AND turn=?', (scope, turn)).fetchone():
                raise CapabilityError('本轮已安排表情或语音，不再追加。')
            bypass_soft = kind=='image' and requested is True
            if kind=='image' and min_reply_gap>0 and not bypass_soft:
                last_image=db.execute("SELECT MAX(stamp) FROM reservations WHERE scope=? AND kind='image'",(scope,)).fetchone()[0]
                if last_image is not None and db.execute('SELECT COUNT(*) FROM reply_turns WHERE scope=? AND stamp>=?',(scope,last_image)).fetchone()[0]<min_reply_gap:
                    raise CapabilityError('距离上次表情的回复轮数不足，这次保持文字。分段不另算一轮。')
            last = db.execute('SELECT MAX(stamp) FROM reservations WHERE scope=?', (scope,)).fetchone()[0]
            if last is not None and now-last < cooldown and not bypass_soft:
                raise CapabilityError('还在发送冷却中，本次保持文字回复。')
            count = db.execute('SELECT COUNT(*) FROM reservations WHERE scope=? AND stamp>?', (scope,now-3600)).fetchone()[0]
            if count >= hourly:
                raise CapabilityError('本小时媒体发送次数已达上限。')
            if asset and db.execute('SELECT 1 FROM reservations WHERE scope=? AND asset=? AND stamp>?', (scope,asset,now-asset_cooldown)).fetchone():
                raise CapabilityError('最近发过同一表情，换一个或保持文字回复。')
            row = db.execute('INSERT INTO reservations(scope,kind,turn,stamp,units,asset) VALUES(?,?,?,?,?,?)', (scope,kind,turn,now,units,asset))
            db.execute('DELETE FROM reservations WHERE stamp<?', (now-86400*35,))
            return row.lastrowid

    def release(self, reservation: int) -> None:
        with self.connect() as db:
            db.execute('DELETE FROM reservations WHERE id=?', (reservation,))

    def recent_assets(self, scope: str, seconds: float = 3600) -> set[str]:
        with self.connect() as db:
            return {row[0] for row in db.execute('SELECT asset FROM reservations WHERE scope=? AND stamp>? AND asset<>?',
                                                  (scope,time.time()-seconds,''))}

    def charge_tts(self, model: str, chars: int, month: str, limit: int) -> None:
        bounded_int(chars,1,2000,'合成字符数')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('CREATE TABLE IF NOT EXISTS tts_budget (model TEXT, month TEXT, chars INTEGER NOT NULL, PRIMARY KEY(model,month))')
            row=db.execute('SELECT chars FROM tts_budget WHERE model=? AND month=?',(model,month)).fetchone()
            used=row[0] if row else 0
            if used+chars>limit:
                raise CapabilityError('本地语音月度预算不足，未提交合成。')
            db.execute('INSERT INTO tts_budget VALUES(?,?,?) ON CONFLICT(model,month) DO UPDATE SET chars=excluded.chars',(model,month,used+chars))

    def refund_tts(self, model: str, chars: int, month: str) -> None:
        with self.connect() as db:
            db.execute('UPDATE tts_budget SET chars=MAX(0,chars-?) WHERE model=? AND month=?',(chars,model,month))
